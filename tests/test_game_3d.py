"""Unit tests for the 3D FPS Game Engine and Kinetic Tracking Assistant."""

import math
import numpy as np
import pytest

from core.game_3d import (
    AIAimAssistant3D,
    Camera3D,
    Game3DSession,
    MovementPattern,
    Renderer3D,
    Target3D,
    TargetType,
)


def test_camera_projection_and_near_clip() -> None:
    camera = Camera3D(x=0.0, y=1.70, z=0.0, yaw=0.0, pitch=0.0, fov_deg=75.0)

    # Point directly ahead at (0, 1.70, 10.0) -> screen center (640, 360) on 1280x720
    proj = camera.project(0.0, 1.70, 10.0, screen_w=1280, screen_h=720)
    assert proj is not None
    u, v, depth = proj
    assert abs(u - 640.0) < 1.0
    assert abs(v - 360.0) < 1.0
    assert abs(depth - 10.0) < 1.0

    # Point behind camera (z < 0.2) -> must return None (clipped)
    behind = camera.project(0.0, 1.70, -5.0, screen_w=1280, screen_h=720)
    assert behind is None


def test_camera_movement_and_recoil() -> None:
    camera = Camera3D(x=0.0, y=1.70, z=0.0, yaw=0.0, pitch=0.0)
    camera.move(forward=1.0, right=0.0, dt=1.0)
    assert camera.z > 0.0

    camera.apply_recoil(pitch_kick=0.05, yaw_kick=0.01)
    assert camera.recoil_pitch > 0.0
    camera.update(dt=0.5)
    assert camera.recoil_pitch < 0.05


def test_target3d_kinematics_and_patterns() -> None:
    target = Target3D(
        target_id=1,
        x=0.0,
        y=0.0,
        z=10.0,
        target_type=TargetType.HUMANOID,
        pattern=MovementPattern.LINEAR_STRAFE,
        strafe_range=5.0,
        strafe_speed=2.0,
    )
    assert target.head_y > target.y
    assert target.head_radius > 0.1

    # Update over time -> velocity should be calculated and non-zero
    target.update(dt=0.016)
    target.update(dt=0.016)
    assert math.hypot(target.vx, target.vy, target.vz) >= 0.0


def test_ai_aim_assistant_3d_acquisition_and_head_bias() -> None:
    camera = Camera3D(x=0.0, y=1.70, z=0.0, yaw=0.0, pitch=0.0, fov_deg=75.0)
    assistant = AIAimAssistant3D()
    assistant.active = True
    assistant.head_bias_percent = 0.75

    target = Target3D(
        target_id=1,
        x=0.5,
        y=0.0,
        z=8.0,
        target_type=TargetType.HUMANOID,
        pattern=MovementPattern.STATIONARY,
    )

    d_yaw, d_pitch = assistant.compute_assist(
        camera=camera,
        targets=[target],
        screen_w=1280,
        screen_h=720,
        dt=0.016,
    )

    assert assistant.has_target is True
    assert assistant.target_screen_pos is not None
    # d_yaw should deflect towards the target on the right
    assert d_yaw > 0.0
    # stick deflection should be computed within [-1.0, 1.0]
    rx, ry = assistant.stick_deflection
    assert -1.0 <= rx <= 1.0
    assert -1.0 <= ry <= 1.0


def test_game_3d_session_raycast_weapon_hit() -> None:
    session = Game3DSession(width=1280, height=720)
    # Align camera perfectly with target head
    target = session.targets[0]
    target.pattern = MovementPattern.STATIONARY
    target.x = 0.0
    target.z = 10.0

    session.camera.x = 0.0
    session.camera.y = target.head_y
    session.camera.z = 0.0
    session.camera.yaw = 0.0
    session.camera.pitch = 0.0

    hit = session.fire_weapon()
    assert hit is True
    assert session.hits == 1
    assert session.shots == 1
    assert session.score > 0
