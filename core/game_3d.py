"""High-Performance 3D FPS Aim Trainer & Kinetic Vision Verification Environment.

This module provides a full 3D first-person shooter arena built specifically
to test and demonstrate:
1. Real-time target acquisition in 3D perspective space.
2. Kinematic velocity prediction (MotionEMA) on moving 3D combat targets.
3. Head-bias vertical targeting math on humanoid targets.
4. Smooth analog stick / camera aim deflection using non-linear response curves.
5. Zero-latency controller input gating (PlayStation DualShock/DualSense & Xbox).
"""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Final, Sequence

import cv2
import numpy as np
import pygame

import config
from bot.gamepad import GamepadManager, GamepadState

__all__ = [
    "AIAimAssistant3D",
    "Camera3D",
    "Game3DSession",
    "MovementPattern",
    "Particle3D",
    "Renderer3D",
    "Target3D",
    "TargetType",
]


class MovementPattern(Enum):
    """Movement pattern for 3D training targets."""

    STATIONARY = auto()
    LINEAR_STRAFE = auto()
    FAST_ZIGZAG = auto()
    ERRATIC_COMBAT = auto()
    ORBITAL_DRONE = auto()


class TargetType(Enum):
    """Target archetype."""

    HUMANOID = auto()
    COMBAT_DRONE = auto()


@dataclass
class Particle3D:
    """3D spark/explosion particle for visual hit confirmation."""

    x: float
    y: float
    z: float
    vx: float
    vy: float
    vz: float
    color: tuple[int, int, int]
    life: float = 0.4
    max_life: float = 0.4
    size: float = 3.0


@dataclass
class Target3D:
    """3D combat dummy or flying target with distinct head & body collision."""

    target_id: int
    x: float = 0.0
    y: float = 0.0
    z: float = 10.0
    vx: float = 0.0
    vy: float = 0.0
    vz: float = 0.0
    width: float = 0.65
    height: float = 1.85
    depth: float = 0.45
    target_type: TargetType = TargetType.HUMANOID
    pattern: MovementPattern = MovementPattern.LINEAR_STRAFE
    max_health: float = 100.0
    health: float = 100.0
    is_alive: bool = True
    hit_flash_timer: float = 0.0
    time_alive: float = 0.0
    base_x: float = 0.0
    base_z: float = 10.0
    strafe_range: float = 6.0
    strafe_speed: float = 3.2

    @property
    def head_y(self) -> float:
        """World Y coordinate of the head center."""
        if self.target_type == TargetType.COMBAT_DRONE:
            return self.y
        return self.y + self.height * 0.85

    @property
    def head_radius(self) -> float:
        """Physical collision radius of the head."""
        return 0.22 if self.target_type == TargetType.HUMANOID else 0.40

    @property
    def body_center_y(self) -> float:
        """World Y coordinate of the torso center."""
        return self.y + self.height * 0.45

    def update(self, dt: float) -> None:
        """Update 3D kinematics and trajectory based on active movement pattern."""
        self.time_alive += dt
        if self.hit_flash_timer > 0:
            self.hit_flash_timer = max(0.0, self.hit_flash_timer - dt)

        prev_x, prev_y, prev_z = self.x, self.y, self.z

        if self.pattern == MovementPattern.STATIONARY:
            self.vx, self.vy, self.vz = 0.0, 0.0, 0.0

        elif self.pattern == MovementPattern.LINEAR_STRAFE:
            # Smooth strafing oscillation left and right
            offset = math.sin(self.time_alive * self.strafe_speed) * self.strafe_range
            self.x = self.base_x + offset
            self.z = self.base_z + math.cos(self.time_alive * 0.8) * 1.5

        elif self.pattern == MovementPattern.FAST_ZIGZAG:
            # Fast tactical strafe with sudden direction changes
            speed_mult = 1.6
            offset = math.sin(self.time_alive * self.strafe_speed * speed_mult) * self.strafe_range
            # Micro jitter simulating evasive maneuvers
            jitter = math.sin(self.time_alive * 9.0) * 0.4
            self.x = self.base_x + offset + jitter
            self.z = self.base_z + math.sin(self.time_alive * 1.5) * 2.5

        elif self.pattern == MovementPattern.ERRATIC_COMBAT:
            # Complex combat movement: strafe, sudden crouch/jump, distance variation
            self.x = self.base_x + math.sin(self.time_alive * 2.8) * 5.0 + math.cos(self.time_alive * 4.5) * 1.5
            self.z = self.base_z + math.cos(self.time_alive * 1.2) * 3.5
            # Jump / duck
            jump_phase = math.sin(self.time_alive * 3.5)
            self.y = max(0.0, jump_phase * 0.8 if jump_phase > 0.4 else 0.0)

        elif self.pattern == MovementPattern.ORBITAL_DRONE:
            radius = 6.5
            self.x = self.base_x + math.sin(self.time_alive * 1.8) * radius
            self.z = self.base_z + math.cos(self.time_alive * 1.8) * (radius * 0.6)
            self.y = 1.5 + math.sin(self.time_alive * 3.0) * 0.9

        effective_dt = max(1e-4, dt)
        self.vx = (self.x - prev_x) / effective_dt
        self.vy = (self.y - prev_y) / effective_dt
        self.vz = (self.z - prev_z) / effective_dt


class Camera3D:
    """First-Person Perspective Camera with 3D projection and look controls."""

    def __init__(
        self,
        x: float = 0.0,
        y: float = 1.70,  # Eye level height in meters
        z: float = 0.0,
        yaw: float = 0.0,
        pitch: float = 0.0,
        fov_deg: float = 75.0,
    ) -> None:
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)
        self.yaw = float(yaw)      # Radians: 0 = +Z forward, >0 = turn right
        self.pitch = float(pitch)  # Radians: 0 = level, >0 = look up, <0 = look down
        self.fov_deg = float(fov_deg)

        # Movement physics
        self.move_speed: float = 6.5
        self.mouse_sensitivity: float = 0.0022
        self.stick_sensitivity: float = 2.4

        # Recoil kickback animation
        self.recoil_pitch: float = 0.0
        self.recoil_yaw: float = 0.0

    def apply_recoil(self, pitch_kick: float = 0.025, yaw_kick: float = 0.008) -> None:
        """Simulate weapon recoil impulse."""
        self.recoil_pitch += pitch_kick
        self.recoil_yaw += (random.random() - 0.5) * yaw_kick

    def update(self, dt: float) -> None:
        """Smoothly recover from recoil kickback."""
        recovery_speed = 12.0 * dt
        if abs(self.recoil_pitch) > 1e-4:
            self.recoil_pitch -= self.recoil_pitch * recovery_speed
        if abs(self.recoil_yaw) > 1e-4:
            self.recoil_yaw -= self.recoil_yaw * recovery_speed

    def project(
        self,
        world_x: float,
        world_y: float,
        world_z: float,
        screen_w: int,
        screen_h: int,
    ) -> tuple[float, float, float] | None:
        """Project a 3D world coordinate to 2D screen coordinates (u, v, depth)."""
        # 1. Translate relative to camera
        dx = world_x - self.x
        dy = world_y - self.y
        dz = world_z - self.z

        effective_yaw = self.yaw + self.recoil_yaw
        effective_pitch = self.pitch + self.recoil_pitch

        # 2. Rotate by yaw (around Y axis)
        cos_y, sin_y = math.cos(effective_yaw), math.sin(effective_yaw)
        x1 = dx * cos_y - dz * sin_y
        z1 = dx * sin_y + dz * cos_y
        y1 = dy

        # 3. Rotate by pitch (around X axis)
        cos_p, sin_p = math.cos(effective_pitch), math.sin(effective_pitch)
        y2 = y1 * cos_p - z1 * sin_p
        z2 = y1 * sin_p + z1 * cos_p
        x2 = x1

        # Near clipping plane (discard points behind camera)
        if z2 <= 0.20:
            return None

        # 4. Perspective projection
        fov_rad = math.radians(self.fov_deg)
        focal_length = (screen_w / 2.0) / math.tan(fov_rad / 2.0)

        screen_u = (x2 * focal_length) / z2 + (screen_w / 2.0)
        screen_v = -(y2 * focal_length) / z2 + (screen_h / 2.0)

        return screen_u, screen_v, z2

    def look(self, d_yaw: float, d_pitch: float) -> None:
        """Rotate camera by relative yaw and pitch deltas."""
        self.yaw += d_yaw
        self.pitch = max(-math.radians(85.0), min(math.radians(85.0), self.pitch + d_pitch))

    def move(self, forward: float, right: float, dt: float) -> None:
        """Move camera relative to current heading on the XZ plane."""
        speed = self.move_speed * dt
        # Heading vector in XZ plane
        sin_y = math.sin(self.yaw)
        cos_y = math.cos(self.yaw)

        self.x += (sin_y * forward + cos_y * right) * speed
        self.z += (cos_y * forward - sin_y * right) * speed

        # Keep player within arena boundaries
        self.x = max(-18.0, min(18.0, self.x))
        self.z = max(-10.0, min(22.0, self.z))


class AIAimAssistant3D:
    """Real-time Kinematic Aim Assistant & Targeting Verification Engine.

    Calculates target head-bias, MotionEMA velocity estimation, and non-linear
    analog stick deflection to demonstrate tracking precision in 3D space.
    """

    def __init__(self) -> None:
        self.active: bool = False
        self.head_bias_percent: float = 0.75
        self.fov_radius_px: float = 280.0
        self.aim_speed: float = 0.35
        self.smoothing: float = 0.45
        self.sensitivity: float = 1.35
        self.power_curve_gamma: float = 1.40
        self.reversal_damping: float = 0.55

        # Telemetry state
        self.has_target: bool = False
        self.target_dist_m: float = 0.0
        self.target_vel_ms: float = 0.0
        self.motion_ema: float = 0.0
        self.aim_delta_px: tuple[float, float] = (0.0, 0.0)
        self.stick_deflection: tuple[float, float] = (0.0, 0.0)
        self.target_screen_pos: tuple[float, float] | None = None
        self.last_sign_x: float = 0.0
        self.last_sign_y: float = 0.0

    def compute_assist(
        self,
        camera: Camera3D,
        targets: Sequence[Target3D],
        screen_w: int,
        screen_h: int,
        dt: float,
    ) -> tuple[float, float]:
        """Compute camera yaw and pitch rotational adjustments towards best 3D target.

        Returns:
            (delta_yaw, delta_pitch) in radians.
        """
        center_x = screen_w / 2.0
        center_y = screen_h / 2.0

        best_target: Target3D | None = None
        best_head_proj: tuple[float, float, float] | None = None
        min_dist_to_crosshair = float("inf")

        for t in targets:
            if not t.is_alive:
                continue

            # Project head and body center
            head_proj = camera.project(t.x, t.head_y, t.z, screen_w, screen_h)
            body_proj = camera.project(t.x, t.body_center_y, t.z, screen_w, screen_h)

            if head_proj is None or body_proj is None:
                continue

            hx, hy, depth = head_proj
            bx, by, _ = body_proj

            # Head-bias vertical interpolation:
            # Target_y = Body_CY - (Body_H * 0.35 * AimBiasPercent)
            estimated_h = abs(by - hy) * 2.0
            target_y = by - (estimated_h * 0.35 * self.head_bias_percent)
            target_x = hx

            dist_to_center = math.hypot(target_x - center_x, target_y - center_y)

            if dist_to_center <= self.fov_radius_px and dist_to_center < min_dist_to_crosshair:
                min_dist_to_crosshair = dist_to_center
                best_target = t
                best_head_proj = (target_x, target_y, depth)

        if best_target is None or best_head_proj is None:
            self.has_target = False
            self.target_screen_pos = None
            self.stick_deflection = (0.0, 0.0)
            return 0.0, 0.0

        target_x, target_y, depth = best_head_proj
        self.has_target = True
        self.target_screen_pos = (target_x, target_y)
        self.target_dist_m = depth

        # Kinematic velocity and EMA
        vel = math.hypot(best_target.vx, best_target.vy, best_target.vz)
        self.target_vel_ms = vel
        alpha = 0.30
        self.motion_ema = alpha * vel + (1.0 - alpha) * self.motion_ema

        # Pixel error from crosshair
        dx = target_x - center_x
        dy = target_y - center_y
        self.aim_delta_px = (dx, dy)

        # Non-linear power curve:
        # Deflection = Sign(Delta) * (|Delta| / FOV)^gamma * Sensitivity
        norm_x = min(1.0, abs(dx) / max(1.0, self.fov_radius_px))
        norm_y = min(1.0, abs(dy) / max(1.0, self.fov_radius_px))

        cur_sign_x = 1.0 if dx >= 0 else -1.0
        cur_sign_y = 1.0 if dy >= 0 else -1.0

        curve_x = cur_sign_x * (norm_x ** self.power_curve_gamma) * self.sensitivity
        curve_y = cur_sign_y * (norm_y ** self.power_curve_gamma) * self.sensitivity

        # Directional reversal damping
        if self.last_sign_x != 0.0 and cur_sign_x != self.last_sign_x:
            curve_x *= self.reversal_damping
        if self.last_sign_y != 0.0 and cur_sign_y != self.last_sign_y:
            curve_y *= self.reversal_damping

        self.last_sign_x = cur_sign_x
        self.last_sign_y = cur_sign_y

        self.stick_deflection = (
            max(-1.0, min(1.0, curve_x)),
            max(-1.0, min(1.0, -curve_y)),
        )

        # Convert deflection to camera angular rotation (radians)
        focal_length = (screen_w / 2.0) / math.tan(math.radians(camera.fov_deg) / 2.0)
        angle_x = math.atan2(dx, focal_length)
        angle_y = math.atan2(-dy, focal_length)

        # Apply smoothing / interpolation
        smooth_factor = max(0.05, min(1.0, self.aim_speed * (1.0 - self.smoothing * 0.7)))
        delta_yaw = angle_x * smooth_factor
        delta_pitch = angle_y * smooth_factor

        return delta_yaw, delta_pitch


class Renderer3D:
    """High-Speed 3D Wireframe & Polarity Shaded Vector Graphics Renderer."""

    def __init__(self, screen: pygame.Surface) -> None:
        self.screen = screen
        self.width = screen.get_width()
        self.height = screen.get_height()
        self.font_large = pygame.font.SysFont("Consolas", 28, bold=True)
        self.font_med = pygame.font.SysFont("Consolas", 18, bold=True)
        self.font_small = pygame.font.SysFont("Consolas", 14)

        # Theme Colors (Deep Cyberpunk)
        self.COLOR_BG = (11, 11, 16)
        self.COLOR_GRID = (30, 35, 55)
        self.COLOR_PILLAR = (45, 50, 75)
        self.COLOR_CYAN = (0, 240, 255)
        self.COLOR_MAGENTA = (255, 0, 255)
        self.COLOR_VIOLET = (138, 43, 226)
        self.COLOR_TARGET_RED = config.TARGET_RED  # (255, 30, 60)
        self.COLOR_HEAD_ACCENT = (255, 100, 120)
        self.COLOR_GREEN = (0, 255, 136)
        self.COLOR_WHITE = (255, 255, 255)

    def draw_arena(self, camera: Camera3D) -> None:
        """Render the 3D perspective floor grid, horizon, and boundaries."""
        self.screen.fill(self.COLOR_BG)

        # Horizon gradient line
        horizon_proj = camera.project(camera.x, 0.0, camera.z + 50.0, self.width, self.height)
        if horizon_proj is not None:
            hy = int(horizon_proj[1])
            if 0 <= hy <= self.height:
                pygame.draw.line(self.screen, (20, 25, 40), (0, hy), (self.width, hy), 2)

        # 3D Floor Grid Lines (Z axis lines)
        for gx in range(-18, 19, 3):
            p1 = camera.project(float(gx), 0.0, -10.0, self.width, self.height)
            p2 = camera.project(float(gx), 0.0, 35.0, self.width, self.height)
            if p1 and p2:
                pygame.draw.line(self.screen, self.COLOR_GRID, (int(p1[0]), int(p1[1])), (int(p2[0]), int(p2[1])), 1)

        # 3D Floor Grid Lines (X axis lines)
        for gz in range(-10, 36, 4):
            p1 = camera.project(-18.0, 0.0, float(gz), self.width, self.height)
            p2 = camera.project(18.0, 0.0, float(gz), self.width, self.height)
            if p1 and p2:
                pygame.draw.line(self.screen, self.COLOR_GRID, (int(p1[0]), int(p1[1])), (int(p2[0]), int(p2[1])), 1)

        # Back Wall Boundary Pillars
        for px in (-18.0, -9.0, 0.0, 9.0, 18.0):
            p_base = camera.project(px, 0.0, 35.0, self.width, self.height)
            p_top = camera.project(px, 7.0, 35.0, self.width, self.height)
            if p_base and p_top:
                pygame.draw.line(
                    self.screen,
                    self.COLOR_PILLAR,
                    (int(p_base[0]), int(p_base[1])),
                    (int(p_top[0]), int(p_top[1])),
                    2,
                )

    def draw_target(self, target: Target3D, camera: Camera3D) -> None:
        """Render a 3D target with distinct Head, Body, and Limbs in true perspective."""
        if not target.is_alive:
            return

        tx, ty, tz = target.x, target.y, target.z
        w2, h, d2 = target.width / 2.0, target.height, target.depth / 2.0

        # Project Head (The primary aim target - colored in solid TARGET_RED)
        head_proj = camera.project(tx, target.head_y, tz, self.width, self.height)
        if head_proj is None:
            return

        hx, hy, depth = head_proj
        # Perspective scaling of head radius
        focal_length = (self.width / 2.0) / math.tan(math.radians(camera.fov_deg) / 2.0)
        proj_head_radius = max(6.0, (target.head_radius * focal_length) / max(0.5, depth))

        # Project Body Bounding Points
        body_top = camera.project(tx, ty + h * 0.75, tz, self.width, self.height)
        body_bottom = camera.project(tx, ty, tz, self.width, self.height)

        if body_top and body_bottom:
            bx, by_top, _ = body_top
            _, by_bottom, _ = body_bottom
            body_h = abs(by_bottom - by_top)
            body_w = max(10.0, (target.width * focal_length) / max(0.5, depth))

            # Body Box (Torso)
            torso_rect = pygame.Rect(
                int(bx - body_w / 2.0),
                int(by_top),
                int(body_w),
                int(body_h * 0.65),
            )
            body_color = (255, 255, 255) if target.hit_flash_timer > 0 else (40, 50, 70)
            pygame.draw.rect(self.screen, body_color, torso_rect, border_radius=4)
            pygame.draw.rect(self.screen, self.COLOR_CYAN, torso_rect, width=2, border_radius=4)

            # Legs
            leg_h = body_h * 0.35
            leg_w = body_w * 0.38
            l_leg = pygame.Rect(int(bx - body_w / 2.0), int(by_top + body_h * 0.65), int(leg_w), int(leg_h))
            r_leg = pygame.Rect(int(bx + body_w / 2.0 - leg_w), int(by_top + body_h * 0.65), int(leg_w), int(leg_h))
            pygame.draw.rect(self.screen, (30, 38, 55), l_leg, border_radius=2)
            pygame.draw.rect(self.screen, (30, 38, 55), r_leg, border_radius=2)

        # Draw Head Hitbox: Vivid Red Circle with Glowing Outline
        head_color = (255, 255, 255) if target.hit_flash_timer > 0 else self.COLOR_TARGET_RED
        pygame.draw.circle(self.screen, head_color, (int(hx), int(hy)), int(proj_head_radius))
        pygame.draw.circle(self.screen, self.COLOR_HEAD_ACCENT, (int(hx), int(hy)), int(proj_head_radius), width=2)
        # Inner bullseye dot
        pygame.draw.circle(self.screen, (255, 220, 220), (int(hx), int(hy)), max(2, int(proj_head_radius * 0.3)))

        # Distance tag above head
        dist_surf = self.font_small.render(f"{depth:.1f}m", True, self.COLOR_CYAN)
        self.screen.blit(dist_surf, (int(hx - dist_surf.get_width() / 2), int(hy - proj_head_radius - 18)))

    def draw_particles(self, particles: list[Particle3D], camera: Camera3D) -> None:
        """Render 3D particles."""
        for p in particles:
            proj = camera.project(p.x, p.y, p.z, self.width, self.height)
            if proj is not None:
                px, py, depth = proj
                alpha = max(0.1, p.life / p.max_life)
                size = max(1.0, (p.size * 200.0) / depth)
                color = tuple(int(c * alpha) for c in p.color)
                pygame.draw.circle(self.screen, color, (int(px), int(py)), max(1, int(size)))

    def draw_hud(
        self,
        camera: Camera3D,
        assistant: AIAimAssistant3D,
        gamepad_state: GamepadState | None,
        score: int,
        hits: int,
        shots: int,
        fps: float,
        bot_mode: bool,
    ) -> None:
        """Render Cyberpunk HUD, Crosshair, and Real-Time Tracking Telemetry."""
        cx, cy = self.width // 2, self.height // 2

        # 1. 3D Crosshair Reticle
        reticle_color = self.COLOR_GREEN if assistant.has_target and assistant.active else self.COLOR_CYAN
        arm_len = 10
        gap = 5
        # Top, Bottom, Left, Right crosshair arms
        pygame.draw.line(self.screen, reticle_color, (cx, cy - gap - arm_len), (cx, cy - gap), 2)
        pygame.draw.line(self.screen, reticle_color, (cx, cy + gap), (cx, cy + gap + arm_len), 2)
        pygame.draw.line(self.screen, reticle_color, (cx - gap - arm_len, cy), (cx - gap, cy), 2)
        pygame.draw.line(self.screen, reticle_color, (cx + gap, cy), (cx + gap + arm_len, cy), 2)
        pygame.draw.circle(self.screen, reticle_color, (cx, cy), 2)

        # Circular FOV Visualization
        if assistant.active:
            fov_color = (0, 255, 136, 40)
            pygame.draw.circle(self.screen, (30, 80, 50), (cx, cy), int(assistant.fov_radius_px), width=1)

        # 2. Tracking Lock Reticle on Target
        if assistant.target_screen_pos is not None:
            tx, ty = assistant.target_screen_pos
            box_sz = 24
            lock_color = self.COLOR_GREEN if assistant.active else (255, 180, 0)
            # Corner brackets around head
            pygame.draw.lines(
                self.screen,
                lock_color,
                False,
                [(tx - box_sz, ty - box_sz + 8), (tx - box_sz, ty - box_sz), (tx - box_sz + 8, ty - box_sz)],
                2,
            )
            pygame.draw.lines(
                self.screen,
                lock_color,
                False,
                [(tx + box_sz - 8, ty - box_sz), (tx + box_sz, ty - box_sz), (tx + box_sz, ty - box_sz + 8)],
                2,
            )
            pygame.draw.lines(
                self.screen,
                lock_color,
                False,
                [(tx - box_sz, ty + box_sz - 8), (tx - box_sz, ty + box_sz), (tx - box_sz + 8, ty + box_sz)],
                2,
            )
            pygame.draw.lines(
                self.screen,
                lock_color,
                False,
                [(tx + box_sz - 8, ty + box_sz), (tx + box_sz, ty + box_sz), (tx + box_sz, ty + box_sz - 8)],
                2,
            )
            # Connecting tracking vector line
            pygame.draw.line(self.screen, lock_color, (cx, cy), (int(tx), int(ty)), 1)

        # 3. Telemetry Card (Top Left)
        card_w, card_h = 340, 210
        card_surf = pygame.Surface((card_w, card_h), pygame.SRCALPHA)
        card_surf.fill((16, 20, 32, 220))
        self.screen.blit(card_surf, (16, 16))
        pygame.draw.rect(self.screen, self.COLOR_VIOLET, (16, 16, card_w, card_h), width=1, border_radius=6)

        title = self.font_large.render("3D AIM VERIFICATION", True, self.COLOR_CYAN)
        self.screen.blit(title, (26, 24))

        status_text = "AUTOBOT TRACKING" if bot_mode else ("ASSIST ENGAGED" if assistant.active else "MANUAL LOOK")
        status_color = self.COLOR_GREEN if (assistant.active or bot_mode) else (150, 150, 170)
        st_surf = self.font_med.render(f"STATUS: {status_text}", True, status_color)
        self.screen.blit(st_surf, (26, 60))

        dist_s = f"TARGET DIST : {assistant.target_dist_m:.2f} m" if assistant.has_target else "TARGET DIST : --"
        self.screen.blit(self.font_small.render(dist_s, True, self.COLOR_WHITE), (26, 88))

        vel_s = f"VELOCITY    : {assistant.target_vel_ms:.2f} m/s (EMA: {assistant.motion_ema:.2f})"
        self.screen.blit(self.font_small.render(vel_s, True, self.COLOR_WHITE), (26, 108))

        rx, ry = assistant.stick_deflection
        stick_s = f"STICK DEFLECT: RX {rx:+.2f} | RY {ry:+.2f}"
        self.screen.blit(self.font_small.render(stick_s, True, self.COLOR_CYAN), (26, 128))

        # Controller connection status
        pad_name = gamepad_state.device_name if (gamepad_state and gamepad_state.connected) else "None (Mouse/KB)"
        pad_s = f"GAMEPAD     : {pad_name}"
        pad_color = self.COLOR_GREEN if (gamepad_state and gamepad_state.connected) else (180, 180, 180)
        self.screen.blit(self.font_small.render(pad_s, True, pad_color), (26, 150))

        bias_s = f"HEAD BIAS   : {assistant.head_bias_percent * 100:.0f}% ANCHOR"
        self.screen.blit(self.font_small.render(bias_s, True, self.COLOR_MAGENTA), (26, 170))

        fps_s = f"FPS: {fps:.0f} | 60Hz TICK"
        self.screen.blit(self.font_small.render(fps_s, True, (100, 255, 100)), (26, 192))

        # 4. Score and Stats (Top Right)
        acc = (hits / max(1, shots)) * 100.0
        score_card = pygame.Surface((220, 95), pygame.SRCALPHA)
        score_card.fill((16, 20, 32, 220))
        self.screen.blit(score_card, (self.width - 236, 16))
        pygame.draw.rect(self.screen, self.COLOR_CYAN, (self.width - 236, 16, 220, 95), width=1, border_radius=6)

        self.screen.blit(self.font_med.render(f"SCORE: {score}", True, self.COLOR_WHITE), (self.width - 224, 26))
        self.screen.blit(self.font_small.render(f"HITS : {hits} / {shots}", True, self.COLOR_WHITE), (self.width - 224, 52))
        self.screen.blit(self.font_small.render(f"ACCURACY : {acc:.1f}%", True, self.COLOR_GREEN), (self.width - 224, 74))

        # 5. Bottom Instructions Bar
        bar_text = (
            "[L2 / RMB] Aim Assist Lock   "
            "[R2 / LMB] Shoot   "
            "[B / F4] Toggle Auto-Bot   "
            "[M / F2] Switch Movement Pattern   "
            "[ESC] Quit"
        )
        bar_surf = self.font_small.render(bar_text, True, (180, 190, 210))
        bar_rect = bar_surf.get_rect(center=(self.width // 2, self.height - 22))
        self.screen.blit(bar_surf, bar_rect)


class Game3DSession:
    """The central 3D Aim Trainer and Real-time Verification Game Loop."""

    def __init__(self, width: int = 1280, height: int = 720) -> None:
        self.width = width
        self.height = height
        self.screen: pygame.Surface | None = None
        self.clock = pygame.time.Clock()
        self.is_running: bool = False

        self.camera = Camera3D(x=0.0, y=1.70, z=0.0)
        self.assistant = AIAimAssistant3D()
        self.gamepad = GamepadManager()
        self.renderer: Renderer3D | None = None

        self.targets: list[Target3D] = []
        self.particles: list[Particle3D] = []

        # Game stats
        self.score: int = 0
        self.hits: int = 0
        self.shots: int = 0
        self.last_shot_time: float = 0.0
        self.bot_mode: bool = False

        self._init_targets()

    def _init_targets(self) -> None:
        """Create initial targets with varied depths and strafe behaviors."""
        self.targets.clear()
        # Primary Humanoid Target (Moves across the room)
        t1 = Target3D(
            target_id=1,
            x=0.0,
            y=0.0,
            z=10.0,
            target_type=TargetType.HUMANOID,
            pattern=MovementPattern.LINEAR_STRAFE,
            base_x=0.0,
            base_z=10.0,
            strafe_range=6.5,
            strafe_speed=3.2,
        )
        # Secondary Combat Drone (Higher up, erratic)
        t2 = Target3D(
            target_id=2,
            x=3.0,
            y=1.8,
            z=15.0,
            target_type=TargetType.COMBAT_DRONE,
            pattern=MovementPattern.FAST_ZIGZAG,
            base_x=0.0,
            base_z=15.0,
            strafe_range=5.0,
            strafe_speed=4.5,
        )
        self.targets.extend([t1, t2])

    def spawn_hit_particles(self, x: float, y: float, z: float, count: int = 18) -> None:
        """Spawn 3D particles upon bullet impact."""
        for _ in range(count):
            self.particles.append(
                Particle3D(
                    x=x,
                    y=y,
                    z=z,
                    vx=(random.random() - 0.5) * 6.0,
                    vy=random.random() * 4.0 + 1.0,
                    vz=(random.random() - 0.5) * 6.0,
                    color=(255, random.randint(50, 180), 30),
                    life=0.35 + random.random() * 0.2,
                    max_life=0.55,
                )
            )

    def fire_weapon(self) -> bool:
        """Perform 3D raycast shot along camera forward axis."""
        now = time.perf_counter()
        if now - self.last_shot_time < 0.12:  # Shot cooldown
            return False

        self.last_shot_time = now
        self.shots += 1
        self.camera.apply_recoil(pitch_kick=0.018, yaw_kick=0.005)

        # Check raycast intersection with targets
        hit_target: Target3D | None = None
        is_headshot = False

        # Ray origin and forward direction in world space
        cos_y, sin_y = math.cos(self.camera.yaw), math.sin(self.camera.yaw)
        cos_p, sin_p = math.cos(self.camera.pitch), math.sin(self.camera.pitch)

        # Camera direction vector
        dir_x = sin_y * cos_p
        dir_y = sin_p
        dir_z = cos_y * cos_p

        min_depth = float("inf")

        for t in self.targets:
            if not t.is_alive:
                continue

            # Vector from camera to target head
            to_head_x = t.x - self.camera.x
            to_head_y = t.head_y - self.camera.y
            to_head_z = t.z - self.camera.z

            # Project onto ray direction
            dot = to_head_x * dir_x + to_head_y * dir_y + to_head_z * dir_z
            if dot > 0.5:
                # Closest point on ray to head center
                close_x = self.camera.x + dir_x * dot
                close_y = self.camera.y + dir_y * dot
                close_z = self.camera.z + dir_z * dot

                dist = math.hypot(t.x - close_x, t.head_y - close_y, t.z - close_z)
                if dist <= t.head_radius * 1.35 and dot < min_depth:
                    min_depth = dot
                    hit_target = t
                    is_headshot = True

        if hit_target is not None:
            self.hits += 1
            hit_target.hit_flash_timer = 0.15
            points = 150 if is_headshot else 50
            self.score += points
            self.spawn_hit_particles(hit_target.x, hit_target.head_y, hit_target.z, 20)
            return True

        return False

    def run(self) -> None:
        """Run the 3D FPS training loop."""
        pygame.init()
        pygame.font.init()
        pygame.display.set_caption("Aim Trainer 3D Arena - Real-time Kinetic Vision & HID")

        self.screen = pygame.display.set_mode((self.width, self.height), pygame.DOUBLEBUF)
        self.renderer = Renderer3D(self.screen)
        self.is_running = True

        # Lock mouse cursor in window
        pygame.event.set_grab(True)
        pygame.mouse.set_visible(False)

        last_time = time.perf_counter()

        while self.is_running:
            cur_time = time.perf_counter()
            dt = min(0.05, cur_time - last_time)
            last_time = cur_time

            # 1. Event Handling
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.is_running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.is_running = False
                    elif event.key in (pygame.K_b, pygame.K_F4):
                        self.bot_mode = not self.bot_mode
                    elif event.key in (pygame.K_m, pygame.K_F2):
                        # Cycle movement pattern
                        patterns = list(MovementPattern)
                        for t in self.targets:
                            idx = (patterns.index(t.pattern) + 1) % len(patterns)
                            t.pattern = patterns[idx]

            # 2. Input Polling (Gamepad & Mouse/Keyboard)
            gamepad_state = self.gamepad.poll()
            mouse_dx, mouse_dy = pygame.mouse.get_rel()
            keys = pygame.key.get_pressed()
            mouse_buttons = pygame.mouse.get_pressed()

            # Camera Look (Right stick / Mouse)
            if gamepad_state.connected and (abs(gamepad_state.right_stick[0]) > 0.05 or abs(gamepad_state.right_stick[1]) > 0.05):
                rx, ry = gamepad_state.right_stick
                self.camera.look(rx * 2.8 * dt, -ry * 2.2 * dt)
            elif abs(mouse_dx) > 0 or abs(mouse_dy) > 0:
                self.camera.look(mouse_dx * self.camera.mouse_sensitivity, -mouse_dy * self.camera.mouse_sensitivity)

            # Camera Movement (Left stick / WASD)
            move_forward = 0.0
            move_right = 0.0

            if gamepad_state.connected and (abs(gamepad_state.left_stick[0]) > 0.08 or abs(gamepad_state.left_stick[1]) > 0.08):
                move_right = gamepad_state.left_stick[0]
                move_forward = -gamepad_state.left_stick[1]
            else:
                if keys[pygame.K_w]: move_forward += 1.0
                if keys[pygame.K_s]: move_forward -= 1.0
                if keys[pygame.K_d]: move_right += 1.0
                if keys[pygame.K_a]: move_right -= 1.0

            if abs(move_forward) > 0 or abs(move_right) > 0:
                self.camera.move(move_forward, move_right, dt)

            # 3. Update Scene Physics & Targets
            for t in self.targets:
                t.update(dt)

            # Update particles
            for p in self.particles:
                p.x += p.vx * dt
                p.y += p.vy * dt
                p.z += p.vz * dt
                p.life -= dt
            self.particles = [p for p in self.particles if p.life > 0]

            self.camera.update(dt)

            # 4. AI Aim Assistant Calculation
            # Trigger gating: Aim assist engages when L2 / LT is pressed or L1 / LB is pressed, or RMB is held, or Bot Mode is ON
            is_aiming = bool(
                self.bot_mode
                or (
                    gamepad_state.connected
                    and (gamepad_state.is_aiming or gamepad_state.left_trigger > 0.15 or gamepad_state.left_bumper)
                )
                or mouse_buttons[2]  # Right Mouse Button
            )
            self.assistant.active = is_aiming

            if is_aiming:
                d_yaw, d_pitch = self.assistant.compute_assist(
                    self.camera, self.targets, self.width, self.height, dt
                )
                self.camera.look(d_yaw, d_pitch)
            else:
                self.assistant.has_target = False
                self.assistant.target_screen_pos = None
                self.assistant.stick_deflection = (0.0, 0.0)

            # Weapon Firing (R2 / RT / R1 / RB / LMB or Auto-Bot)
            is_firing = bool(
                (self.bot_mode and self.assistant.has_target and math.hypot(*self.assistant.aim_delta_px) < 18.0)
                or (
                    gamepad_state.connected
                    and (gamepad_state.is_firing or gamepad_state.right_trigger > 0.15 or gamepad_state.right_bumper)
                )
                or mouse_buttons[0]  # Left Mouse Button
            )
            if is_firing:
                self.fire_weapon()

            # 5. Render Scene
            self.renderer.draw_arena(self.camera)

            # Sort targets by depth (far to near for painter's algorithm)
            sorted_targets = sorted(
                self.targets,
                key=lambda t: math.hypot(t.x - self.camera.x, t.z - self.camera.z),
                reverse=True,
            )
            for t in sorted_targets:
                self.renderer.draw_target(t, self.camera)

            self.renderer.draw_particles(self.particles, self.camera)

            fps = self.clock.get_fps()
            self.renderer.draw_hud(
                camera=self.camera,
                assistant=self.assistant,
                gamepad_state=gamepad_state,
                score=self.score,
                hits=self.hits,
                shots=self.shots,
                fps=fps,
                bot_mode=self.bot_mode,
            )

            pygame.display.flip()
            self.clock.tick(120)  # High-refresh 120 FPS execution

        pygame.quit()
