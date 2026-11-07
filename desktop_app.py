"""تطبيق سطح المكتب الاحترافي: واجهة Cyberpunk HUD المعربة والمتجاوبة مع الشاشة بالكامل."""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wintypes
import subprocess
import sys
import threading
import time
import tkinter as tk
import tkinter.colorchooser as colorchooser
from pathlib import Path
from tkinter import messagebox
from typing import Any

import customtkinter as ctk

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config
from bot.capture import (
    enable_dpi_awareness,
    find_window_info,
    find_window_region,
    screen_fov_region,
    virtual_screen_rect,
)
from bot.gamepad import HidHideManager
from bot.remote_play import (
    is_ps5_client_installed,
    is_xbox_client_installed,
    launch_ps5_client,
    launch_xbox_client,
    open_psn_lookup_tool,
    optimize_chiaki_settings,
)
from bot.worker import BotWorker

# ── لوحة الألوان الزرقاء التكتيكية (VORTX Tactical Cobalt Blue Theme) ─────
CLR_BG_DARK     = "#070B14"   # خلفية كحلية داكنة عميقة (Deep Tactical Navy)
CLR_CARD_BG     = "#0E1726"   # بطاقات أزرق داكن فخم (Midnight Cobalt Card)
CLR_CARD_BORDER = "#1E2E4A"   # حدود البطاقات بلون أزرق كحلي صلب
CLR_CARD_ACTIVE = "#172A4E"   # بطاقة نشطة متوهجة بالأزرق (Active Cobalt Highlight)
CLR_ACCENT_BLUE = "#2563EB"   # أزرق كهربائي تكتيكي أساسي (Electric Royal Blue)
CLR_ACCENT_CYAN = "#00D2FF"   # سماوي نيون متوهج نشط (Cyan Glow / Ice Blue)
CLR_ACCENT_HOVR = "#3B82F6"   # تفاعل المؤشر بالأزرق الساطع (Hover Light Blue)
CLR_BLUE_HOVR   = "#1D4ED8"   # أزرق عميق للتفاعل
CLR_TEXT_WHITE  = "#FFFFFF"   # نصوص أساسية بيضاء
CLR_TEXT_MUTED  = "#94A3B8"   # نصوص فرعية رمادية مائلة للأزرق (Slate Text)
CLR_TEXT_DARK   = "#64748B"   # نصوص ثانوية خافتة
CLR_SUCCESS_GRN = "#10B981"   # أخضر نيون للحالة النشطة
CLR_DANGER_RED  = "#EF4444"   # أحمر للتوقف والطوارئ
CLR_INPUT_BG    = "#0A1220"   # حقول الإدخال والبطاقات الداخلية (Deep Slate Input)

# التوافق مع المتغيرات السابقة (Backward-Compatibility Aliases)
CLR_ACCENT_PURP = CLR_ACCENT_BLUE
CLR_ACCENT_VIOL = CLR_ACCENT_CYAN
CLR_CYAN_HOVR   = CLR_ACCENT_HOVR

VK_F6 = 0x75


# ── الدوال المساعدة (Helpers) ──────────────────────────────────────────────

def hex_to_rgb(h: str) -> config.RGB | None:
    """تحويل كود اللون السداسي (Hex) إلى ثلاثية RGB."""
    h = h.strip().lstrip("#")
    if len(h) != 6:
        return None
    try:
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
    except ValueError:
        return None


def rgb_to_hex(rgb: config.RGB) -> str:
    """تحويل ثلاثية RGB إلى كود سداسي #rrggbb."""
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def get_pixel_at_cursor() -> tuple[int, int, int] | None:
    """قراءة لون البكسل الفعلي تحت مؤشر الماوس بدقة عبر Win32 API."""
    class POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

    pt = POINT()
    if not ctypes.windll.user32.GetCursorPos(ctypes.byref(pt)):
        return None
    hdc = ctypes.windll.user32.GetDC(0)
    if not hdc:
        return None
    try:
        colorref = ctypes.windll.gdi32.GetPixel(hdc, pt.x, pt.y)
        if colorref == 0xFFFFFFFF:
            return None
        r = colorref & 0xFF
        g = (colorref >> 8) & 0xFF
        b = (colorref >> 16) & 0xFF
        return (r, g, b)
    finally:
        ctypes.windll.user32.ReleaseDC(0, hdc)


def list_visible_windows() -> list[tuple[int, str]]:
    """استرجاع قائمة بكافة النوافذ الظاهرة النشطة على نظام ويندوز."""
    user32 = ctypes.windll.user32
    results: list[tuple[int, str]] = []

    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def _cb(hwnd: int, _: int) -> bool:
        if user32.IsWindowVisible(ctypes.c_void_p(hwnd)):
            length = user32.GetWindowTextLengthW(ctypes.c_void_p(hwnd))
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(ctypes.c_void_p(hwnd), buf, length + 1)
                title = buf.value.strip()
                if title:
                    results.append((hwnd, title))
        return True

    user32.EnumWindows(WNDENUMPROC(_cb), 0)
    return results


# ── نافذة شفافة لبرامج الالتقاط لمنع الاستنساخ الذاتي ──────────────────────────

def make_window_transparent_to_capture(hwnd: int) -> bool:
    """Exclude the window from screen capture so it never captures its own UI (avoids recursive cloning)."""
    try:
        if hasattr(ctypes, "windll") and hasattr(ctypes.windll, "user32"):
            # WDA_EXCLUDEFROMCAPTURE = 0x00000011 (Windows 10 2004+)
            return bool(ctypes.windll.user32.SetWindowDisplayAffinity(ctypes.c_void_p(hwnd), 0x00000011))
    except Exception:
        pass
    return False


# ── شاشة المعاينة المنبثقة العائمة (Mini Floating HUD) ──────────────────────

class MiniFloatingHUD:
    """نافذة HUD مصغرة تطفو دائماً فوق اللعبة أو تطبيق Chiaki."""

    def __init__(self, app: "AimBotDesktopApp") -> None:
        self.app = app
        self.root = app.root
        self.win = tk.Toplevel(self.root)
        self.win.title("Aim Bot Mini HUD")
        self.win.geometry("340x390+50+50")
        self.win.configure(bg=CLR_BG_DARK)
        self.win.attributes("-topmost", True)
        self.win.minsize(280, 260)

        self._drag_start_x = 0
        self._drag_start_y = 0

        self._build_ui()
        self.win.protocol("WM_DELETE_WINDOW", self.close)
        try:
            self.win.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(self.win.winfo_id()) or self.win.winfo_id()
            make_window_transparent_to_capture(hwnd)
        except Exception:
            pass

    def _build_ui(self) -> None:
        hdr = tk.Frame(self.win, bg=CLR_CARD_BG, cursor="fleur", pady=6)
        hdr.pack(fill="x")
        hdr.bind("<Button-1>", self._start_drag)
        hdr.bind("<B1-Motion>", self._do_drag)

        lbl = tk.Label(
            hdr, text="🎯 شاشة الرصد المنبثقة [HUD]",
            font=("Segoe UI", 10, "bold"), fg=CLR_ACCENT_VIOL, bg=CLR_CARD_BG
        )
        lbl.pack(side="left", padx=10)
        lbl.bind("<Button-1>", self._start_drag)
        lbl.bind("<B1-Motion>", self._do_drag)

        btn_close = tk.Button(
            hdr, text="✕", font=("Segoe UI", 9, "bold"), fg=CLR_TEXT_MUTED,
            bg=CLR_CARD_BG, bd=0, padx=6, cursor="hand2", command=self.close
        )
        btn_close.pack(side="right", padx=6)

        prev_box = tk.Frame(self.win, bg="#05070A", bd=1, relief="solid")
        prev_box.pack(fill="both", expand=True, padx=8, pady=(6, 4))

        self.lbl_preview = tk.Label(
            prev_box, text="بث الرؤية المباشر (60 إطار/ث)...", font=("Segoe UI", 9),
            fg=CLR_TEXT_MUTED, bg="#05070A"
        )
        self.lbl_preview.pack(fill="both", expand=True)

        status_row = tk.Frame(self.win, bg=CLR_CARD_BG, pady=4)
        status_row.pack(fill="x", padx=8, pady=2)

        self.lbl_status = tk.Label(
            status_row, textvariable=self.app.badge_status_var,
            font=("Segoe UI", 9, "bold"), fg="#fff", bg=CLR_ACCENT_PURP, padx=8, pady=2
        )
        self.lbl_status.pack(side="left", padx=4)

        self.lbl_fps = tk.Label(
            status_row, textvariable=self.app.badge_fps_var,
            font=("Consolas", 9, "bold"), fg=CLR_TEXT_WHITE, bg=CLR_INPUT_BG, padx=6, pady=2
        )
        self.lbl_fps.pack(side="left", padx=2)

        chiaki_hud_row = tk.Frame(self.win, bg=CLR_INPUT_BG, pady=2)
        chiaki_hud_row.pack(fill="x", padx=8, pady=(1, 3))

        self.lbl_chiaki = tk.Label(
            chiaki_hud_row, textvariable=self.app.chiaki_hud_var,
            font=("Segoe UI", 8, "bold"), fg=CLR_SUCCESS_GRN, bg=CLR_INPUT_BG
        )
        self.lbl_chiaki.pack(side="left", padx=6)

        tk.Button(
            chiaki_hud_row, text="🔗 ربط Chiaki", font=("Segoe UI", 8, "bold"),
            bg=CLR_ACCENT_PURP, fg="#fff", bd=0, padx=6, pady=2, cursor="hand2",
            command=self.app.auto_detect_chiaki
        ).pack(side="right", padx=4)

        ctrl_row = tk.Frame(self.win, bg=CLR_BG_DARK, pady=4)
        ctrl_row.pack(fill="x", padx=8, pady=2)

        self.btn_toggle = tk.Button(
            ctrl_row, text="⚡ تشغيل [F6]", font=("Segoe UI", 10, "bold"),
            bg=CLR_ACCENT_PURP, fg="#fff", bd=0, padx=10, pady=5, cursor="hand2",
            command=self.app.toggle_bot
        )
        self.btn_toggle.pack(side="left", fill="x", expand=True, padx=(0, 4))

        tk.Button(
            ctrl_row, text="🔙 الرئيسية", font=("Segoe UI", 9),
            bg=CLR_CARD_BG, fg=CLR_TEXT_WHITE, bd=0, padx=8, pady=5, cursor="hand2",
            command=self.close
        ).pack(side="left")

    def _start_drag(self, event) -> None:
        self._drag_start_x = event.x
        self._drag_start_y = event.y

    def _do_drag(self, event) -> None:
        x = self.win.winfo_x() + (event.x - self._drag_start_x)
        y = self.win.winfo_y() + (event.y - self._drag_start_y)
        self.win.geometry(f"+{x}+{y}")

    def update_frame(self, photo: tk.PhotoImage) -> None:
        if self.win.winfo_exists():
            self.lbl_preview.config(image=photo, text="")

    def update_status(self, is_enabled: bool) -> None:
        if self.win.winfo_exists():
            if is_enabled:
                self.btn_toggle.config(text="🛑 إيقاف [F6]", bg=CLR_DANGER_RED)
                self.lbl_status.config(bg=CLR_SUCCESS_GRN, text="● نشط")
            else:
                self.btn_toggle.config(text="⚡ تشغيل [F6]", bg=CLR_ACCENT_PURP)
                self.lbl_status.config(bg=CLR_ACCENT_PURP, text="○ جاهز")

    def close(self) -> None:
        self.app._mini_hud = None
        self.win.destroy()
        self.root.deiconify()


# ── التطبيق الرئيسي المتجاوب بالكامل (Main Desktop App) ──────────────────────

class AimBotDesktopApp:
    SRC_FOV    = "fov"
    SRC_WINDOW = "window"

    def __init__(self, root: tk.Tk | ctk.CTk | None = None) -> None:
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        if root is None:
            self.root = ctk.CTk()
        else:
            self.root = root

        self.root.title("🎯 بوت التصويب التكتيكي الذكي // Cyberpunk HUD")
        self.root.geometry("1060x760")
        self.root.minsize(560, 560)
        self.root.configure(bg=CLR_BG_DARK)
        enable_dpi_awareness()
        try:
            self.root.update_idletasks()
            self.root.lift()
            self.root.focus_force()
            self.root.attributes("-topmost", True)
            self.root.after(400, lambda: self.root.attributes("-topmost", False))
        except Exception:
            pass

        self.cfg = config.Config.load()
        self.cfg.bot_enabled = False

        # متغيرات الحالة
        self.fov_size_var          = tk.StringVar(value="500")
        self.src_mode              = tk.StringVar(value=self.SRC_FOV)
        self.preview_var           = tk.BooleanVar(value=True)
        self._active_src_mode      = self.SRC_FOV
        self._active_fov_size      = "500"
        self._active_preview_only  = True
        self.auto_click_var        = tk.BooleanVar(value=True)
        self.ai_var                = tk.BooleanVar(value=bool(getattr(self.cfg, "ai_assistant", True)))
        self.aim_speed_var         = tk.DoubleVar(value=float(self.cfg.aim_speed))
        self.smoothing_var         = tk.DoubleVar(value=float(self.cfg.smoothing))
        self.tolerance_var         = tk.DoubleVar(value=float(getattr(self.cfg, "color_tolerance_h", 10.0)))
        self.fov_radius_var        = tk.DoubleVar(value=float(getattr(self.cfg, "fov_radius_px", 250.0)))
        self.max_area_var          = tk.DoubleVar(value=float(getattr(self.cfg, "max_target_area_px", 5000.0)))
        self.vertical_offset_var   = tk.DoubleVar(value=float(getattr(self.cfg, "vertical_offset_px", 0.0)))
        self.auto_track_var        = tk.BooleanVar(value=bool(getattr(self.cfg, "auto_track_enabled", True)))
        self.controller_mode_var   = tk.BooleanVar(value=bool(getattr(self.cfg, "controller_mode", True)))
        self.controller_lt_aim_var = tk.BooleanVar(value=bool(getattr(self.cfg, "controller_lt_aim", True)))
        self.input_mode_var        = tk.StringVar(value="controller" if self.controller_mode_var.get() else "mouse")
        self.status_text           = tk.StringVar(value="وضع المعاينة الآمن نشط — لا يتم إرسال نقرات أو تحريك للماوس")

        # نمط الشدة وأولوية الاستهداف
        self.intensity_var         = tk.StringVar(value=str(getattr(self.cfg, "intensity_profile", "NORMAL")))
        self.target_priority_var   = tk.StringVar(value=str(getattr(self.cfg, "target_priority", "CHEST")))

        # تعيين أزرار يد التحكم
        bindings = getattr(self.cfg, "controller_bindings", dict(config.CONTROLLER_BINDINGS))
        self.binding_vars: dict[str, tk.StringVar] = {
            "AIM_TRIGGER": tk.StringVar(value=str(getattr(self.cfg, "aim_trigger", bindings.get("AIM_TRIGGER", "LT")))),
            "FIRE_TRIGGER": tk.StringVar(value=str(getattr(self.cfg, "fire_trigger", bindings.get("FIRE_TRIGGER", "RT")))),
            "TACTICAL_JUMP": tk.StringVar(value=str(bindings.get("TACTICAL_JUMP", "L2"))),
            "SLIDE_CANCEL_PRONE": tk.StringVar(value=str(bindings.get("SLIDE_CANCEL_PRONE", "R3"))),
            "MELEE_ACTION": tk.StringVar(value=str(bindings.get("MELEE_ACTION", "R2"))),
        }
        self.stick_sens_var        = tk.DoubleVar(value=float(getattr(self.cfg, "stick_sensitivity", bindings.get("STICK_SENSITIVITY", 1.25))))
        self.stick_smooth_var      = tk.DoubleVar(value=float(getattr(self.cfg, "stick_smoothing", bindings.get("STICK_SMOOTHING", 0.35))))
        self.deadzone_var          = tk.DoubleVar(value=float(bindings.get("DEADZONE_PX", 3.0)))

        # متغيرات القياس الحية (Telemetry)
        self.badge_status_var      = tk.StringVar(value="○ جاهز")
        self.badge_fps_var         = tk.StringVar(value="0.0 إطار/ث")
        self.badge_latency_var     = tk.StringVar(value="0.0 ms")
        self.badge_controller_var  = tk.StringVar(value="🎮 فحص اليد...")
        self.controller_hud_var    = tk.StringVar(value="🎮 يد التحكم: جاري الفحص...")
        self.chiaki_hud_var        = tk.StringVar(value="🔍 بانتظار ربط Chiaki")
        self.disable_mouse_var     = tk.BooleanVar(value=bool(getattr(self.cfg, "disable_mouse_movement", False)))
        self.roboflow_ai_var       = tk.BooleanVar(value=bool(getattr(self.cfg, "use_roboflow_ai", False)))
        self.power_exponent_var    = tk.DoubleVar(value=float(getattr(self.cfg, "power_exponent", 1.40)))
        self.reversal_damp_var     = tk.DoubleVar(value=float(getattr(self.cfg, "reversal_damping", 0.40)))
        self.recoil_v_var          = tk.DoubleVar(value=float(getattr(self.cfg, "recoil_vertical_px", 0.0)))
        self.recoil_h_var          = tk.DoubleVar(value=float(getattr(self.cfg, "recoil_horizontal_px", 0.0)))
        self.recoil_delay_var      = tk.DoubleVar(value=float(getattr(self.cfg, "recoil_delay_ms", 0.0)))
        self.stick_breakaway_var   = tk.DoubleVar(value=float(getattr(self.cfg, "stick_min_breakaway", 0.08)))
        self.trigger_thresh_var    = tk.DoubleVar(value=float(getattr(self.cfg, "trigger_threshold", 0.15)))
        self.head_bias_var         = tk.DoubleVar(value=float(getattr(self.cfg, "head_bias_percent", 0.70)))
        self.triggerbot_var        = tk.BooleanVar(value=bool(getattr(self.cfg, "triggerbot_enabled", False)))
        self.ps5_status_var        = tk.StringVar(value="🎮 Chiaki PS5: جاهز للتشغيل والربط")
        self.static_rejection_var  = tk.BooleanVar(value=bool(getattr(self.cfg, "static_prop_rejection", True)))
        self.capture_backend_var   = tk.StringVar(value=str(getattr(self.cfg, "capture_backend", "auto")))
        self.local_ai_var          = tk.BooleanVar(value=bool(getattr(self.cfg, "use_local_ai", False)))
        self.hidhide_mgr           = HidHideManager()
        self.badge_hidhide_var     = tk.StringVar(value="🛡️ فحص HidHide...")
        self._mini_hud: MiniFloatingHUD | None = None

        # حالة ربط النوافذ
        self._window_title: str = ""
        self._locked_hwnd: int | None = None

        # حالة اللون المرصود
        saved_color = getattr(self.cfg, "target_color", None)
        if isinstance(saved_color, (list, tuple)) and len(saved_color) == 3:
            self._tracked_color = (int(saved_color[0]), int(saved_color[1]), int(saved_color[2]))
        else:
            self._tracked_color = hex_to_rgb("eb4341") or config.TARGET_RED
        self.cfg.target_color = self._tracked_color
        self._eyedropper_active = False

        self._preview_photo: tk.PhotoImage | None = None

        # حاويات البطاقات التفاعلية
        self._intensity_cards: dict[str, ctk.CTkFrame] = {}
        self._target_cards: dict[str, ctk.CTkFrame] = {}

        # تهيئة عامل الخلفية (Bot Worker)
        self.worker: BotWorker | None = None
        self._init_worker()
        if self.worker is not None:
            self.worker.set_preview_only(True)

        # حالة التبويبات
        self._active_tab = 0
        self._tab_frames: list[ctk.CTkScrollableFrame] = []
        self._tab_buttons: list[ctk.CTkButton] = []

        # المكونات المتجاوبة للوحة المعاينة والتحكم
        self._main_content_grid: ctk.CTkFrame | None = None
        self._panel_controls: ctk.CTkFrame | None = None
        self._panel_preview: ctk.CTkFrame | None = None
        self._current_layout_cols: int = 0

        # بناء الواجهة
        self._build_ui()

        # خيط الاستماع لمفتاح F6
        self._hotkey_running = True
        self._hotkey_thread = threading.Thread(target=self._hotkey_listener, daemon=True)
        self._hotkey_thread.start()

        self.root.bind("<space>", self._on_space_pressed)
        self.root.bind("<Configure>", self._on_window_resize)

        # حلقات التحديث الفوري
        self.root.after(20, self._update_preview_feed)
        self.root.after(300, self._update_status_ui)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── إدارة عامل الخلفية (Worker Management) ────────────────────────────
    def _init_worker(self) -> None:
        if self.worker is not None:
            self.worker.stop()
            self.worker = None

        if self._active_src_mode == self.SRC_WINDOW and self._window_title:
            def region_getter():
                reg = find_window_region(self._window_title)
                if reg is None:
                    # عند إغلاق أو عدم توفر نافذة Chiaki، الرجوع تلقائياً لوسط الشاشة حتى لا يتوقف البوت
                    fov_px = int(self._active_fov_size)
                    return screen_fov_region(fov_px, fov_px)
                return reg
            def hwnd_getter():
                return self._locked_hwnd or 0
        else:
            fov_px = int(self._active_fov_size)
            def region_getter():
                return screen_fov_region(fov_px, fov_px)
            def hwnd_getter():
                return 0

        self.worker = BotWorker(
            cfg=self.cfg,
            window_handle_getter=hwnd_getter,
            region_getter=region_getter,
            on_stop=self._on_worker_emergency_stop,
        )
        self.worker.set_preview_only(self._active_preview_only)
        self.worker.start()

    def _on_worker_emergency_stop(self, reason: str) -> None:
        self.cfg.bot_enabled = False
        self._refresh_toggle_btn()
        self.status_text.set(f"⚠️ توقف طوارئ: {reason}")
        self.badge_status_var.set("⚠️ توقف طوارئ")

    # ═══════════════════════════════════════════════════════════════════════
    # بناء الواجهة المتجاوبة بالكامل (Responsive Cyberpunk Architecture)
    # ═══════════════════════════════════════════════════════════════════════

    def _build_ui(self) -> None:
        # ── 1. الشريط العلوي والعنوان ──────────────────────────────────────
        hdr = ctk.CTkFrame(self.root, fg_color=CLR_BG_DARK, corner_radius=0)
        hdr.pack(fill="x", padx=12, pady=(6, 2))

        top_row = ctk.CTkFrame(hdr, fg_color="transparent")
        top_row.pack(fill="x")

        title_box = ctk.CTkFrame(top_row, fg_color="transparent")
        title_box.pack(side="left")

        ctk.CTkLabel(
            title_box, text="🎯 VORTX TACTICAL VISION",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color=CLR_TEXT_WHITE,
        ).pack(side="left", padx=(0, 6))

        ctk.CTkLabel(
            title_box, text="// COBALT BLUE HUD",
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
            text_color=CLR_ACCENT_CYAN,
        ).pack(side="left", padx=(0, 8))

        hw_badge = ctk.CTkLabel(
            title_box, text="🔒 مقفل على هذا العتاد",
            font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
            fg_color="#0F2042", text_color="#7DD3FC", corner_radius=6, padx=8, pady=2
        )
        hw_badge.pack(side="left", padx=2)

        ctrl_box = ctk.CTkFrame(top_row, fg_color="transparent")
        ctrl_box.pack(side="right")

        self.lbl_badge_status = ctk.CTkLabel(
            ctrl_box, textvariable=self.badge_status_var,
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            fg_color=CLR_CARD_BG, text_color=CLR_ACCENT_VIOL,
            corner_radius=6, padx=8, pady=3,
        )
        self.lbl_badge_status.pack(side="left", padx=3)

        self.lbl_badge_fps = ctk.CTkLabel(
            ctrl_box, textvariable=self.badge_fps_var,
            font=ctk.CTkFont(family="Consolas", size=10, weight="bold"),
            fg_color=CLR_CARD_BG, text_color=CLR_TEXT_WHITE,
            corner_radius=6, padx=6, pady=3,
        )
        self.lbl_badge_fps.pack(side="left", padx=3)

        self.lbl_badge_lat = ctk.CTkLabel(
            ctrl_box, textvariable=self.badge_latency_var,
            font=ctk.CTkFont(family="Consolas", size=10, weight="bold"),
            fg_color=CLR_CARD_BG, text_color=CLR_TEXT_MUTED,
            corner_radius=6, padx=6, pady=3,
        )
        self.lbl_badge_lat.pack(side="left", padx=3)

        ctk.CTkButton(
            ctrl_box, text="🪟 شاشة HUD المنبثقة",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            fg_color=CLR_CARD_BG, hover_color=CLR_ACCENT_PURP, text_color=CLR_TEXT_WHITE,
            border_width=1, border_color=CLR_CARD_BORDER, corner_radius=6,
            width=115, height=26, command=self.open_mini_hud
        ).pack(side="left", padx=3)

        # ── 2. شريط معايرة الألوان المتجاوب ────────────────────────────────
        calib_bar = ctk.CTkFrame(self.root, fg_color=CLR_CARD_BG, corner_radius=8, border_width=1, border_color=CLR_CARD_BORDER)
        calib_bar.pack(fill="x", padx=12, pady=(2, 4))

        row_c1 = ctk.CTkFrame(calib_bar, fg_color="transparent")
        row_c1.pack(fill="x", padx=8, pady=(4, 2))

        ctk.CTkLabel(
            row_c1, text="🎨 لون الهدف المطلوب تتبعه:",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=CLR_TEXT_WHITE,
        ).pack(side="left", padx=(0, 6))

        self.color_swatch = tk.Label(
            row_c1, width=4, height=1, bg=rgb_to_hex(self._tracked_color),
            relief="solid", bd=1
        )
        self.color_swatch.pack(side="left", padx=(0, 6))

        ctk.CTkLabel(row_c1, text="#", font=ctk.CTkFont(family="Consolas", size=12, weight="bold"), text_color=CLR_TEXT_MUTED).pack(side="left")
        self.color_entry_var = tk.StringVar(value=rgb_to_hex(self._tracked_color).lstrip("#"))
        self.color_entry = ctk.CTkEntry(
            row_c1, textvariable=self.color_entry_var, width=75, height=24,
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
            fg_color=CLR_INPUT_BG, border_color=CLR_CARD_BORDER
        )
        self.color_entry.pack(side="left", padx=(2, 6))
        self.color_entry.bind("<Return>", lambda e: self._apply_color())

        ctk.CTkButton(
            row_c1, text="تطبيق", width=55, height=24,
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            fg_color=CLR_ACCENT_PURP, hover_color=CLR_ACCENT_HOVR,
            command=self._apply_color
        ).pack(side="left", padx=(0, 6))

        self.btn_eyedropper = ctk.CTkButton(
            row_c1, text="🎯 قطارة الشاشة [Space]", width=140, height=24,
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            fg_color=CLR_INPUT_BG, hover_color=CLR_CARD_BORDER,
            border_width=1, border_color=CLR_ACCENT_VIOL,
            command=self._toggle_eyedropper
        )
        self.btn_eyedropper.pack(side="left", padx=(0, 6))

        # قوالب الألوان في سطر مرن
        row_c2 = ctk.CTkFrame(calib_bar, fg_color="transparent")
        row_c2.pack(fill="x", padx=8, pady=(0, 4))

        preset_colors = [
            ("🌸 ماجنتا كود", "ff00ff"),
            ("🔴 ريموت بلاي", "eb4341"),
            ("🔴 ايم لاب", "ff3b30"),
            ("🔴 أحمر فاقع", "ff2d2d"),
            ("🟠 برتقالي", "ff6600"),
            ("🟡 أصفر نيون", "e5ff00"),
            ("🔵 سماوي", "00f0ff"),
        ]
        for idx, (lbl, hx) in enumerate(preset_colors):
            row_c2.grid_columnconfigure(idx, weight=1)
            ctk.CTkButton(
                row_c2, text=lbl, height=22,
                font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
                fg_color=CLR_INPUT_BG, hover_color=CLR_CARD_BORDER,
                command=lambda h=hx: self._set_color_preset(h)
            ).grid(row=0, column=idx, padx=2, sticky="nsew")

        # ── 3. الحاوية الرئيسية لجسم التطبيق (Main Body Frame) ─────────────
        self.main_body = ctk.CTkFrame(self.root, fg_color="transparent")
        self.main_body.pack(fill="both", expand=True, padx=12, pady=(0, 4))

        # ── 3.1 القائمة الجانبية على اليسار (Left Sidebar Menu) ────────────
        self.sidebar_left = ctk.CTkFrame(
            self.main_body, fg_color=CLR_CARD_BG, corner_radius=10,
            border_width=1, border_color=CLR_CARD_BORDER, width=255
        )
        self.sidebar_left.pack(side="left", fill="y", padx=(0, 6))
        self.sidebar_left.pack_propagate(False)
        self.sidebar_right = self.sidebar_left  # مرجع للتوافقية

        # عنوان القائمة الجانبية
        sb_title_box = ctk.CTkFrame(self.sidebar_left, fg_color="transparent")
        sb_title_box.pack(fill="x", padx=10, pady=(10, 6))
        ctk.CTkLabel(
            sb_title_box, text="⚙️ لوحة التحكم والإعدادات",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=CLR_ACCENT_CYAN,
        ).pack(anchor="w")

        # أزرار التشغيل والربط
        self.btn_main_toggle = ctk.CTkButton(
            self.sidebar_left, text="⚡ تشغيل بوت التصويب [F6]", height=38,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color=CLR_ACCENT_BLUE, hover_color=CLR_ACCENT_HOVR,
            command=self.toggle_bot
        )
        self.btn_main_toggle.pack(fill="x", padx=10, pady=(2, 6))

        self.btn_chiaki = ctk.CTkButton(
            self.sidebar_left, text="🎮 ربط Chiaki / PS5", height=34,
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            fg_color=CLR_INPUT_BG, hover_color=CLR_CARD_BORDER,
            border_width=1, border_color=CLR_SUCCESS_GRN, text_color=CLR_SUCCESS_GRN,
            command=self.auto_detect_chiaki
        )
        self.btn_chiaki.pack(fill="x", padx=10, pady=(0, 8))

        # خط فاصل تكتيكي
        sep = ctk.CTkFrame(self.sidebar_left, height=1, fg_color=CLR_CARD_BORDER)
        sep.pack(fill="x", padx=10, pady=(0, 8))

        ctk.CTkLabel(
            self.sidebar_left, text="القوائم وألواح التخصيص",
            font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
            text_color=CLR_TEXT_DARK,
        ).pack(anchor="w", padx=12, pady=(0, 4))

        # أزرار القائمة العمودية (Vertical Menu Buttons)
        tabs_data = [
            ("📺 شاشة المعاينة الكبيرة", 0),
            ("🎯 التصويب والفيزياء", 1),
            ("🎮 يد التحكم والإدخال", 2),
            ("💥 مانع الارتداد المزدوج", 3),
            ("🎨 الرؤية والذكاء الاصطناعي", 4),
            ("🏆 بروفايلات الألعاب والأدوات", 5),
        ]

        self._tab_buttons = []
        for text, idx in tabs_data:
            btn = ctk.CTkButton(
                self.sidebar_left, text=text,
                font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
                fg_color=CLR_INPUT_BG, text_color=CLR_TEXT_MUTED,
                hover_color=CLR_CARD_ACTIVE, corner_radius=6, height=36,
                anchor="w",
                command=lambda i=idx: self._switch_tab(i)
            )
            btn.pack(fill="x", padx=10, pady=3)
            self._tab_buttons.append(btn)

        # خط فاصل قبل خيارات الأمان السفلية
        sep2 = ctk.CTkFrame(self.sidebar_left, height=1, fg_color=CLR_CARD_BORDER)
        sep2.pack(fill="x", padx=10, pady=(8, 6))

        # مفاتيح التبديل السريعة
        toggles_box = ctk.CTkFrame(self.sidebar_left, fg_color="transparent")
        toggles_box.pack(fill="x", padx=10, pady=(0, 6))

        ctk.CTkSwitch(
            toggles_box, text="🛡️ وضع المعاينة الآمن",
            variable=self.preview_var, command=self._on_preview_toggle,
            progress_color=CLR_ACCENT_CYAN,
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
        ).pack(anchor="w", pady=3)

        ctk.CTkSwitch(
            toggles_box, text="🚫 حظر ماوس اللاب",
            variable=self.disable_mouse_var, command=self._on_disable_mouse_toggle,
            progress_color=CLR_ACCENT_CYAN,
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
        ).pack(anchor="w", pady=3)

        ctk.CTkButton(
            self.sidebar_left, text="🪟 شاشة HUD المصغرة", height=28,
            font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
            fg_color=CLR_INPUT_BG, hover_color=CLR_CARD_ACTIVE,
            border_width=1, border_color=CLR_CARD_BORDER, text_color=CLR_ACCENT_CYAN,
            command=self.open_mini_hud
        ).pack(fill="x", padx=10, pady=(4, 8))

        # ── 3.2 الحاوية العامة المتمددة للشاشة أو لوحة الإعدادات ────────────
        self.tab_container = ctk.CTkFrame(self.main_body, fg_color=CLR_BG_DARK, corner_radius=10)
        self.tab_container.pack(side="right", fill="both", expand=True)

        self._build_tab_preview_stream()
        self._build_tab_aim_kinematics()
        self._build_tab_controller_input()
        self._build_tab_anti_recoil()
        self._build_tab_vision_ai()
        self._build_tab_game_profiles_tools()

        self._switch_tab(0)

        # ── 4. شريط الحالة السفلي (Footer) ─────────────────────────────────
        ftr = ctk.CTkFrame(self.root, fg_color=CLR_CARD_BG, corner_radius=6, border_width=1, border_color=CLR_CARD_BORDER)
        ftr.pack(fill="x", padx=12, pady=(0, 6))

        self.lbl_status = ctk.CTkLabel(
            ftr, textvariable=self.status_text,
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=CLR_TEXT_MUTED, anchor="w"
        )
        self.lbl_status.pack(anchor="w", padx=10, pady=4)

    # ── التبديل بين التبويبات ──────────────────────────────────────────────
    def _switch_tab(self, index: int) -> None:
        self._active_tab = index
        for i, frame in enumerate(self._tab_frames):
            if i == index:
                frame.pack(fill="both", expand=True)
                if i < len(self._tab_buttons):
                    self._tab_buttons[i].configure(
                        fg_color=CLR_CARD_ACTIVE, text_color=CLR_ACCENT_CYAN,
                        border_width=1, border_color=CLR_ACCENT_CYAN
                    )
            else:
                frame.pack_forget()
                if i < len(self._tab_buttons):
                    self._tab_buttons[i].configure(
                        fg_color=CLR_INPUT_BG, text_color=CLR_TEXT_MUTED,
                        border_width=0
                    )

    def _add_tab_return_banner(self, parent_frame: Any, title: str) -> None:
        """إضافة شريط علوي بارز في كل لوحة إعدادات للعودة الفورية إلى شاشة المعاينة الكبيرة."""
        ret_bar = ctk.CTkFrame(
            parent_frame, fg_color=CLR_CARD_BG, corner_radius=8,
            border_width=1, border_color=CLR_CARD_BORDER
        )
        ret_bar.pack(fill="x", padx=4, pady=(2, 8))

        ctk.CTkButton(
            ret_bar, text="⬅️ العودة إلى شاشة العرض الكبيرة",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color=CLR_ACCENT_BLUE, hover_color=CLR_ACCENT_HOVR,
            text_color=CLR_TEXT_WHITE, height=30, corner_radius=6,
            command=lambda: self._switch_tab(0)
        ).pack(side="left", padx=8, pady=5)

        ctk.CTkLabel(
            ret_bar, text=title,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=CLR_ACCENT_CYAN
        ).pack(side="right", padx=10)

    # ── معالجة تكبير وتصغير النافذة بمرونة (Responsive Layout Switcher) ─────
    def _on_window_resize(self, event=None) -> None:
        pass

    # ═══════════════════════════════════════════════════════════════════════
    # التبويب 0: شاشة المعاينة الكبيرة والبث المباشر (Big Screen Preview)
    # ═══════════════════════════════════════════════════════════════════════

    def _build_tab_preview_stream(self) -> None:
        f = ctk.CTkFrame(self.tab_container, fg_color=CLR_BG_DARK, corner_radius=8)
        self._tab_frames.append(f)

        # مقابض التوافق الخلفي
        self._main_content_grid = f
        self._panel_controls = f

        cam_card = self._make_card(f)
        self._panel_preview = cam_card
        cam_card.pack(fill="both", expand=True, padx=4, pady=4)

        self._card_header(cam_card, "🎥 البث المباشر لكاميرا الرصد (60 إطار/ث - شاشة كاملة)", color=CLR_ACCENT_CYAN)

        self.preview_canvas_box = tk.Frame(cam_card, bg="#05070A", bd=2, relief="solid")
        self.preview_canvas_box.pack(fill="both", expand=True, padx=8, pady=(4, 6))

        self.preview_display_label = tk.Label(
            self.preview_canvas_box, text="في انتظار الإطارات المباشرة...\n(تأكد من تفعيل المعاينة أو تشغيل البوت)",
            font=("Segoe UI", 12, "bold"), fg=CLR_TEXT_MUTED, bg="#05070A"
        )
        self.preview_display_label.pack(fill="both", expand=True)

        # شريط رادار الاستهداف والتحليل اللحظي
        radar_bar = ctk.CTkFrame(cam_card, fg_color="transparent")
        radar_bar.pack(fill="x", padx=8, pady=(0, 4))

        self.lbl_radar_target = ctk.CTkLabel(
            radar_bar, text="حالة الهدف: جاهز للرصد والتقاط الإطارات",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color=CLR_TEXT_WHITE, anchor="w"
        )
        self.lbl_radar_target.pack(side="left")

        # شريط اختيار النافذة وأدوات البث
        win_bar = ctk.CTkFrame(cam_card, fg_color="transparent")
        win_bar.pack(fill="x", padx=8, pady=(0, 6))

        self.lbl_win_status = ctk.CTkLabel(
            win_bar, text="🎯 النافذة النشطة: وسط الشاشة (نطاق FOV)",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color=CLR_TEXT_MUTED, anchor="w"
        )
        self.lbl_win_status.pack(side="left")

        ctk.CTkButton(
            win_bar, text="🪟 اختيار نافذة أخرى", width=125, height=26,
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            fg_color=CLR_INPUT_BG, hover_color=CLR_CARD_BORDER,
            border_width=1, border_color=CLR_CARD_BORDER,
            command=self._show_window_picker
        ).pack(side="right", padx=(4, 0))

        ctk.CTkButton(
            win_bar, text="📖 دليل Call of Duty", width=130, height=26,
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            fg_color=CLR_INPUT_BG, hover_color=CLR_CARD_BORDER,
            border_width=1, border_color=CLR_ACCENT_BLUE,
            command=self._show_ingame_guide
        ).pack(side="right")

    # ═══════════════════════════════════════════════════════════════════════
    # التبويب 1: التصويب والفيزياء والانحراف (Aim & Kinematics)
    # ═══════════════════════════════════════════════════════════════════════

    def _build_tab_aim_kinematics(self) -> None:
        f = ctk.CTkScrollableFrame(self.tab_container, fg_color=CLR_BG_DARK, corner_radius=0)
        self._tab_frames.append(f)
        self._add_tab_return_banner(f, "🎯 لوحة إعدادات التصويب والفيزياء والانحراف")

        # 1. شبكة أنماط الشدة والسرعة
        int_card = self._make_card(f)
        self._card_header(int_card, "⚡ أنماط الشدة والسرعة (Aim Intensity Presets)", color=CLR_ACCENT_CYAN)

        grid_int = ctk.CTkFrame(int_card, fg_color="transparent")
        grid_int.pack(fill="x", padx=8, pady=(0, 6))

        profiles = [
            ("SOFT", "ناعم", "سرعة 0.20\nسلاسة 0.70\nنطاق 160"),
            ("NORMAL", "متوازن", "سرعة 0.35\nسلاسة 0.50\nنطاق 220"),
            ("MEDIUM", "سريع", "سرعة 0.55\nسلاسة 0.35\nنطاق 300"),
            ("SUPER", "خارق", "سرعة 0.85\nسلاسة 0.15\nنطاق 450"),
        ]

        for idx, (pcode, ptitle, psub) in enumerate(profiles):
            grid_int.grid_columnconfigure(idx, weight=1)
            card_btn = ctk.CTkFrame(
                grid_int, fg_color=CLR_INPUT_BG, corner_radius=8,
                border_width=1, border_color=CLR_CARD_BORDER, cursor="hand2"
            )
            card_btn.grid(row=0, column=idx, padx=2, pady=2, sticky="nsew")
            self._intensity_cards[pcode] = card_btn

            lbl_title = ctk.CTkLabel(
                card_btn, text=ptitle, font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                text_color=CLR_TEXT_WHITE
            )
            lbl_title.pack(pady=(5, 1))

            lbl_sub = ctk.CTkLabel(
                card_btn, text=psub,
                font=ctk.CTkFont(family="Consolas", size=9), text_color=CLR_TEXT_MUTED
            )
            lbl_sub.pack(pady=(0, 5))

            for w in (card_btn, lbl_title, lbl_sub):
                w.bind("<Button-1>", lambda e, n=pcode: self._select_intensity(n))

        # 2. شبكة أولوية منطقة الاستهداف
        tgt_card = self._make_card(f)
        self._card_header(tgt_card, "🎯 أولوية منطقة الاستهداف (Target Priority)", color=CLR_ACCENT_BLUE)

        grid_tgt = ctk.CTkFrame(tgt_card, fg_color="transparent")
        grid_tgt.pack(fill="x", padx=8, pady=(0, 6))

        targets = [
            ("MARKER", "🎯 علامة اللاعب", "قفل مباشر ودقيق على علامة/أيقونة اللاعب"),
            ("HEAD", "👤 الرأس", "قفل مباشر لمنطقة الرأس والعنق مع إمكانية تعديل الإزاحة"),
            ("CHEST", "🛡️ الصدر", "القفل التكتيكي الثابت على مركز الكتلة"),
            ("RANDOM", "🎲 عشوائي", "محاكاة التباين البشري الطبيعي بين الصدر والرأس"),
        ]

        for idx, (tcode, ttitle, tdesc) in enumerate(targets):
            grid_tgt.grid_columnconfigure(idx, weight=1)
            tcard = ctk.CTkFrame(
                grid_tgt, fg_color=CLR_INPUT_BG, corner_radius=8,
                border_width=1, border_color=CLR_CARD_BORDER, cursor="hand2"
            )
            tcard.grid(row=0, column=idx, padx=2, pady=2, sticky="nsew")
            self._target_cards[tcode] = tcard

            lbl_t = ctk.CTkLabel(
                tcard, text=ttitle, font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                text_color=CLR_TEXT_WHITE
            )
            lbl_t.pack(pady=(5, 1))

            lbl_d = ctk.CTkLabel(
                tcard, text=tdesc,
                font=ctk.CTkFont(family="Segoe UI", size=9), text_color=CLR_TEXT_MUTED,
                wraplength=180
            )
            lbl_d.pack(pady=(0, 5), padx=4)

            for w in (tcard, lbl_t, lbl_d):
                w.bind("<Button-1>", lambda e, n=tcode: self._select_target_priority(n))

        self._refresh_intensity_cards()
        self._refresh_target_cards()

        # 3. أشرطة التمرير والتحكم الدقيق
        slider_card = self._make_card(f)
        self._card_header(slider_card, "🎛️ أشرطة التحكم والضبط التكتيكي (Tactical Aim Sliders)", color=CLR_ACCENT_CYAN)

        # نطاق الدائرة (FOV)
        fov_row = ctk.CTkFrame(slider_card, fg_color="transparent")
        fov_row.pack(fill="x", padx=10, pady=3)

        self.lbl_fov_slider = ctk.CTkLabel(
            fov_row, text=f"نطاق دائرة التصويب: {int(self.fov_radius_var.get())} بكسل",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color=CLR_TEXT_WHITE
        )
        self.lbl_fov_slider.pack(side="left")

        self.sw_auto_track = ctk.CTkSwitch(
            fov_row, text="تتبع تلقائي", variable=self.auto_track_var,
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            progress_color=CLR_ACCENT_CYAN, command=self._on_auto_track_toggle
        )
        self.sw_auto_track.pack(side="right")

        self.slider_fov = ctk.CTkSlider(
            slider_card, from_=50.0, to=600.0, number_of_steps=55,
            variable=self.fov_radius_var, command=self._on_fov_slider_drag,
            progress_color=CLR_ACCENT_BLUE, button_color=CLR_ACCENT_CYAN,
            button_hover_color=CLR_ACCENT_HOVR, fg_color=CLR_CARD_BORDER
        )
        self.slider_fov.pack(fill="x", padx=10, pady=(2, 6))

        # الإزاحة الرأسية (Vertical Offset)
        self.lbl_offset_slider = ctk.CTkLabel(
            slider_card, text=f"الإزاحة الرأسية للرأس: {int(self.vertical_offset_var.get())} بكسل",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color=CLR_TEXT_WHITE,
            anchor="w"
        )
        self.lbl_offset_slider.pack(anchor="w", padx=10, pady=(2, 0))

        self.slider_offset = ctk.CTkSlider(
            slider_card, from_=-50.0, to=50.0, number_of_steps=100,
            variable=self.vertical_offset_var, command=self._on_vertical_offset_drag,
            progress_color=CLR_ACCENT_BLUE, button_color=CLR_ACCENT_CYAN,
            button_hover_color=CLR_ACCENT_HOVR, fg_color=CLR_CARD_BORDER
        )
        self.slider_offset.pack(fill="x", padx=10, pady=(2, 6))

        # سلاسة التصويب (Aim Smoothing)
        self.lbl_smooth_slider = ctk.CTkLabel(
            slider_card, text=f"سلاسة التصويب: {self.smoothing_var.get():.2f}",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color=CLR_TEXT_WHITE,
            anchor="w"
        )
        self.lbl_smooth_slider.pack(anchor="w", padx=10, pady=(2, 0))

        self.slider_smooth = ctk.CTkSlider(
            slider_card, from_=0.10, to=1.00, number_of_steps=90,
            variable=self.smoothing_var, command=self._on_smooth_slider_drag,
            progress_color=CLR_ACCENT_BLUE, button_color=CLR_ACCENT_CYAN,
            button_hover_color=CLR_ACCENT_HOVR, fg_color=CLR_CARD_BORDER
        )
        self.slider_smooth.pack(fill="x", padx=10, pady=(2, 8))

        # 4. بطاقة كينماتيكا ومنحنيات الحركة المتقدمة (VORTX Kinematics & Advanced Physics)
        kin_card = self._make_card(f)
        self._card_header(kin_card, "🧠 كينماتيكا ومنحنيات الاستجابة الحركية (Kinematics & Ballistics)", color=CLR_ACCENT_BLUE)

        # POWER CURVE EXPONENT (VORTX Kinematics)
        self.lbl_power_exp = ctk.CTkLabel(
            kin_card, text=f"منحنى القوة اللاخطي (Power Curve Exponent): {self.power_exponent_var.get():.2f}",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color=CLR_TEXT_WHITE,
            anchor="w"
        )
        self.lbl_power_exp.pack(anchor="w", padx=10, pady=(2, 0))

        ctk.CTkSlider(
            kin_card, from_=1.00, to=2.50, number_of_steps=30,
            variable=self.power_exponent_var, command=self._on_power_exponent_drag,
            progress_color=CLR_ACCENT_BLUE, button_color=CLR_ACCENT_CYAN,
            button_hover_color=CLR_ACCENT_HOVR, fg_color=CLR_CARD_BORDER
        ).pack(fill="x", padx=10, pady=(2, 6))

        # REVERSAL DAMPING (Directional Damping)
        self.lbl_reversal_damp = ctk.CTkLabel(
            kin_card, text=f"كبح الارتداد العكسي (Reversal Damping): {self.reversal_damp_var.get():.2f}",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color=CLR_TEXT_WHITE,
            anchor="w"
        )
        self.lbl_reversal_damp.pack(anchor="w", padx=10, pady=(2, 0))

        ctk.CTkSlider(
            kin_card, from_=0.10, to=1.00, number_of_steps=18,
            variable=self.reversal_damp_var, command=self._on_reversal_damp_drag,
            progress_color=CLR_ACCENT_CYAN, button_color=CLR_ACCENT_BLUE,
            button_hover_color=CLR_ACCENT_HOVR, fg_color=CLR_CARD_BORDER
        ).pack(fill="x", padx=10, pady=(2, 6))

        # HEAD-BIAS AIM HEIGHT
        self.lbl_head_bias = ctk.CTkLabel(
            kin_card, text=f"إزاحة الاستهداف نحو الرأس (Head-Bias Offset): {int(self.head_bias_var.get() * 100)}%",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color=CLR_TEXT_WHITE,
            anchor="w"
        )
        self.lbl_head_bias.pack(anchor="w", padx=10, pady=(2, 0))

        ctk.CTkSlider(
            kin_card, from_=0.00, to=1.00, number_of_steps=20,
            variable=self.head_bias_var, command=self._on_head_bias_drag,
            progress_color=CLR_ACCENT_BLUE, button_color=CLR_ACCENT_CYAN,
            button_hover_color=CLR_ACCENT_HOVR, fg_color=CLR_CARD_BORDER
        ).pack(fill="x", padx=10, pady=(2, 6))

        # STATIC PROP REJECTION SWITCH
        ctk.CTkSwitch(
            kin_card, text="🛡️ تصفية المجسمات والأهداف الثابتة (Static Prop Filter)",
            variable=self.static_rejection_var, command=self._toggle_static_rejection,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=CLR_TEXT_WHITE, progress_color=CLR_SUCCESS_GRN,
        ).pack(anchor="w", padx=10, pady=(4, 6))

    # ═══════════════════════════════════════════════════════════════════════
    # التبويب 2: يد التحكم والإدخال وعتبة الزناد (Controller & Input)
    # ═══════════════════════════════════════════════════════════════════════

    def _build_tab_controller_input(self) -> None:
        f = ctk.CTkScrollableFrame(self.tab_container, fg_color=CLR_BG_DARK, corner_radius=0)
        self._tab_frames.append(f)
        self._add_tab_return_banner(f, "🎮 لوحة عتاد يد التحكم والإدخال المزدوج")

        # ── 1. بطاقة عتاد يد التحكم ومحرك الإدخال ─────────────────────────────
        hw_card = self._make_card(f)
        self._card_header(hw_card, "🎮 عتاد يد التحكم ومحرك الإدخال (Hardware & Input Engine)", color=CLR_ACCENT_CYAN)

        mode_row = ctk.CTkFrame(hw_card, fg_color="transparent")
        mode_row.pack(fill="x", padx=10, pady=(0, 6))

        ctk.CTkRadioButton(
            mode_row, text="🎮 يد التحكم الافتراضية (vgamepad / DualShock 4)",
            variable=self.input_mode_var, value="controller",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color=CLR_ACCENT_CYAN, hover_color=CLR_ACCENT_BLUE,
            command=self._on_input_mode_change
        ).pack(side="left", padx=(0, 16))

        ctk.CTkRadioButton(
            mode_row, text="🖱️ محاكاة الماوس (SendInput)",
            variable=self.input_mode_var, value="mouse",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color=CLR_ACCENT_CYAN, hover_color=CLR_ACCENT_BLUE,
            command=self._on_input_mode_change
        ).pack(side="left")

        ctrl_type_row = ctk.CTkFrame(hw_card, fg_color="transparent")
        ctrl_type_row.pack(fill="x", padx=10, pady=(2, 6))

        ctk.CTkLabel(
            ctrl_type_row, text="نوع اليد الافتراضية المصدرة للعبة:",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"), text_color=CLR_TEXT_MUTED
        ).pack(side="left", padx=(0, 8))

        ctk.CTkSegmentedButton(
            ctrl_type_row,
            values=["Sony DualSense (PS5/DS4)", "Xbox 360 Controller"],
            command=self._on_controller_type_change,
            selected_color=CLR_ACCENT_BLUE,
            selected_hover_color=CLR_ACCENT_CYAN,
        ).pack(side="left")

        self.lbl_ctrl_telemetry = ctk.CTkLabel(
            hw_card, textvariable=self.controller_hud_var,
            font=ctk.CTkFont(family="Consolas", size=10, weight="bold"),
            fg_color=CLR_INPUT_BG, text_color=CLR_ACCENT_CYAN,
            corner_radius=6, padx=10, pady=5
        )
        self.lbl_ctrl_telemetry.pack(anchor="w", padx=10, pady=(0, 6))

        # ── 2. بطاقة تعيين الأزرار والزناد ─────────────────────────────────
        map_card = self._make_card(f)
        self._card_header(map_card, "🕹️ لوحة تعيين الأزرار والزناد (Control Mapping Panel)", color=CLR_ACCENT_BLUE)

        pr_bar = ctk.CTkFrame(map_card, fg_color="transparent")
        pr_bar.pack(fill="x", padx=10, pady=(0, 6))

        ctk.CTkLabel(
            pr_bar, text="تخطيطات جاهزة:",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"), text_color=CLR_TEXT_MUTED
        ).pack(side="left", padx=(0, 6))

        for pname, pbind in [
            ("سوني الافتراضي (L2/R2)", {"AIM_TRIGGER": "L2", "FIRE_TRIGGER": "R2", "TACTICAL_JUMP": "Cross", "SLIDE_CANCEL_PRONE": "Circle", "MELEE_ACTION": "R3"}),
            ("سوني المعكوس (L1/R1)", {"AIM_TRIGGER": "L1", "FIRE_TRIGGER": "R1", "TACTICAL_JUMP": "Cross", "SLIDE_CANCEL_PRONE": "Circle", "MELEE_ACTION": "R3"}),
            ("سوني ذكي (L2 أو L1)", {"AIM_TRIGGER": "L2_OR_L1", "FIRE_TRIGGER": "R2_OR_R1", "TACTICAL_JUMP": "Cross", "SLIDE_CANCEL_PRONE": "R3", "MELEE_ACTION": "Circle"}),
            ("بمبر جمبر تاكتيكال", {"AIM_TRIGGER": "L2", "FIRE_TRIGGER": "R2", "TACTICAL_JUMP": "L1", "SLIDE_CANCEL_PRONE": "R3", "MELEE_ACTION": "R1"}),
        ]:
            ctk.CTkButton(
                pr_bar, text=pname, height=24,
                font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
                fg_color=CLR_INPUT_BG, hover_color=CLR_CARD_BORDER,
                border_width=1, border_color=CLR_ACCENT_BLUE,
                command=lambda b=pbind: self._apply_controller_preset(b)
            ).pack(side="left", padx=2)

        ps_buttons_full = [
            "L2", "R2", "L1", "R1", "R3", "L3",
            "Cross", "Circle", "Square", "Triangle",
            "L2_OR_L1", "R2_OR_R1",
            "DPAD_UP", "DPAD_DOWN", "DPAD_LEFT", "DPAD_RIGHT",
            "LT", "RT", "LB", "RB", "Always", "LMB", "RMB",
        ]

        mappings = [
            ("AIM_TRIGGER", "🎯 زر التصويب وقفل الهدف [Aim]:", ps_buttons_full),
            ("FIRE_TRIGGER", "💥 زر إطلاق النار المخصص [Fire]:", ps_buttons_full),
            ("TACTICAL_JUMP", "🦘 القفز التكتيكي [Tactical Jump]:", ps_buttons_full),
            ("SLIDE_CANCEL_PRONE", "⚡ الانزلاق والانبطاح السريع [Slide Cancel]:", ps_buttons_full),
            ("MELEE_ACTION", "🗡️ الضرب والقتال القريب [Melee Action]:", ps_buttons_full),
        ]

        for key, label, opts in mappings:
            row = ctk.CTkFrame(map_card, fg_color=CLR_INPUT_BG, corner_radius=6)
            row.pack(fill="x", padx=10, pady=3)

            ctk.CTkLabel(
                row, text=label, width=225, anchor="w",
                font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
                text_color=CLR_TEXT_WHITE
            ).pack(side="left", padx=8, pady=4)

            btn_detect = ctk.CTkButton(
                row, text="🎮 تعيين بالضغط", width=105, height=26,
                font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
                fg_color=CLR_CARD_BG, hover_color=CLR_CARD_BORDER,
                border_width=1, border_color=CLR_ACCENT_CYAN, text_color=CLR_ACCENT_CYAN,
            )
            btn_detect.configure(command=lambda k=key, b=btn_detect: self._listen_for_controller_bind(k, b))
            btn_detect.pack(side="right", padx=(4, 8), pady=4)

            opt_menu = ctk.CTkOptionMenu(
                row, values=opts, variable=self.binding_vars[key],
                width=115, height=26,
                font=ctk.CTkFont(family="Consolas", size=10, weight="bold"),
                fg_color=CLR_CARD_BG, button_color=CLR_ACCENT_BLUE,
                button_hover_color=CLR_ACCENT_HOVR,
                dropdown_fg_color=CLR_CARD_BG,
                dropdown_hover_color=CLR_ACCENT_BLUE,
                dropdown_text_color=CLR_TEXT_WHITE,
                command=lambda val, k=key: self._on_binding_change(k, val)
            )
            opt_menu.pack(side="right", padx=4, pady=4)

        # ── 3. بطاقة حساسية عصا التحكم وعتبة الاستجابة ─────────────────────
        sens_card = self._make_card(f)
        self._card_header(sens_card, "🎛️ ضبط حساسية وتنعيم عصا التحكم (Stick Sensitivity & Response)", color=CLR_ACCENT_CYAN)

        # STICK_SENSITIVITY: 0.1 to 3.0
        self.lbl_sens = ctk.CTkLabel(
            sens_card, text=f"حساسية عصا التحكم (STICK_SENSITIVITY): {self.stick_sens_var.get():.2f}x",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color=CLR_TEXT_WHITE,
            anchor="w"
        )
        self.lbl_sens.pack(anchor="w", padx=10, pady=(3, 0))

        ctk.CTkSlider(
            sens_card, from_=0.10, to=3.00, number_of_steps=58,
            variable=self.stick_sens_var, command=self._on_stick_sens_drag,
            progress_color=CLR_ACCENT_CYAN, button_color=CLR_ACCENT_BLUE,
            button_hover_color=CLR_ACCENT_HOVR, fg_color=CLR_CARD_BORDER
        ).pack(fill="x", padx=10, pady=(2, 6))

        # STICK_SMOOTHING: 0.05 to 1.0
        self.lbl_stick_smooth = ctk.CTkLabel(
            sens_card, text=f"تنعيم استجابة العصا (STICK_SMOOTHING): {self.stick_smooth_var.get():.2f}",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color=CLR_TEXT_WHITE,
            anchor="w"
        )
        self.lbl_stick_smooth.pack(anchor="w", padx=10, pady=(3, 0))

        ctk.CTkSlider(
            sens_card, from_=0.05, to=1.00, number_of_steps=95,
            variable=self.stick_smooth_var, command=self._on_stick_smoothing_drag,
            progress_color=CLR_ACCENT_BLUE, button_color=CLR_ACCENT_CYAN,
            button_hover_color=CLR_CYAN_HOVR, fg_color=CLR_CARD_BORDER
        ).pack(fill="x", padx=10, pady=(2, 6))

        # DEADZONE
        self.lbl_deadzone = ctk.CTkLabel(
            sens_card, text=f"منطقة الموت للأنالوج (DEADZONE_PX): {int(self.deadzone_var.get())} بكسل",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color=CLR_TEXT_WHITE,
            anchor="w"
        )
        self.lbl_deadzone.pack(anchor="w", padx=10, pady=(2, 0))

        ctk.CTkSlider(
            sens_card, from_=0.0, to=15.0, number_of_steps=15,
            variable=self.deadzone_var, command=self._on_deadzone_drag,
            progress_color=CLR_ACCENT_CYAN, button_color=CLR_ACCENT_BLUE,
            button_hover_color=CLR_ACCENT_HOVR, fg_color=CLR_CARD_BORDER
        ).pack(fill="x", padx=10, pady=(2, 6))

        # STICK BREAKAWAY BOOST (Anti-Deadzone punch-through)
        self.lbl_breakaway = ctk.CTkLabel(
            sens_card, text=f"دفعة كسر منطقة الموت (Anti-Deadzone Punch): {self.stick_breakaway_var.get():.2f}",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color=CLR_TEXT_WHITE,
            anchor="w"
        )
        self.lbl_breakaway.pack(anchor="w", padx=10, pady=(2, 0))

        ctk.CTkSlider(
            sens_card, from_=0.00, to=0.25, number_of_steps=25,
            variable=self.stick_breakaway_var, command=self._on_stick_breakaway_drag,
            progress_color=CLR_ACCENT_CYAN, button_color=CLR_ACCENT_BLUE,
            button_hover_color=CLR_CYAN_HOVR, fg_color=CLR_CARD_BORDER
        ).pack(fill="x", padx=10, pady=(2, 6))

        # TRIGGER THRESHOLD (Hair-Trigger vs Deep Press)
        self.lbl_trigger_thresh = ctk.CTkLabel(
            sens_card, text=f"عتبة استجابة زناد L2/R2 (Trigger Threshold): {int(self.trigger_thresh_var.get() * 100)}%",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color=CLR_TEXT_WHITE,
            anchor="w"
        )
        self.lbl_trigger_thresh.pack(anchor="w", padx=10, pady=(2, 0))

        ctk.CTkSlider(
            sens_card, from_=0.02, to=0.40, number_of_steps=38,
            variable=self.trigger_thresh_var, command=self._on_trigger_thresh_drag,
            progress_color=CLR_ACCENT_CYAN, button_color=CLR_ACCENT_BLUE,
            button_hover_color=CLR_ACCENT_HOVR, fg_color=CLR_CARD_BORDER
        ).pack(fill="x", padx=10, pady=(2, 6))

        # ── 4. بطاقة الإطلاق التلقائي (Triggerbot) ─────────────────────────
        tb_card = self._make_card(f)
        self._card_header(tb_card, "⚡ الإطلاق التلقائي التنافسي (Triggerbot Auto-Fire)", color=CLR_DANGER_RED)

        ctk.CTkSwitch(
            tb_card, text="💥 النقر والإطلاق التلقائي عند مطابقة الهدف بالمنتصف [Triggerbot Auto-Fire]",
            variable=self.triggerbot_var, command=self._toggle_triggerbot,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=CLR_TEXT_WHITE, progress_color=CLR_DANGER_RED,
        ).pack(anchor="w", padx=10, pady=(4, 6))

    # ═══════════════════════════════════════════════════════════════════════
    # التبويب 3: مانع الارتداد المزدوج والتأخير (Dual-Axis Anti-Recoil)
    # ═══════════════════════════════════════════════════════════════════════

    def _build_tab_anti_recoil(self) -> None:
        f = ctk.CTkScrollableFrame(self.tab_container, fg_color=CLR_BG_DARK, corner_radius=0)
        self._tab_frames.append(f)
        self._add_tab_return_banner(f, "💥 لوحة إعدادات مانع الارتداد المزدوج والتأخير")

        # ── بطاقة مانع الارتداد المزدوج (Dual-Axis Anti-Recoil System) ──
        recoil_card = self._make_card(f)
        self._card_header(recoil_card, "💥 مانع الارتداد التلقائي المزدوج (Dual-Axis Anti-Recoil)", color=CLR_ACCENT_HOVR)

        ctk.CTkLabel(
            recoil_card, text="يعمل تلقائياً عند ضغط زناد إطلاق النار (R2 / RT) لسحب السلاح بدقة وتثبيت النقطة",
            font=ctk.CTkFont(family="Segoe UI", size=10), text_color=CLR_TEXT_MUTED
        ).pack(anchor="w", padx=10, pady=(0, 4))

        # أزرار قوالب الارتداد السريعة
        rec_preset_bar = ctk.CTkFrame(recoil_card, fg_color="transparent")
        rec_preset_bar.pack(fill="x", padx=10, pady=(0, 6))

        ctk.CTkLabel(
            rec_preset_bar, text="قوالب ارتداد جاهزة:",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"), text_color=CLR_TEXT_MUTED
        ).pack(side="left", padx=(0, 6))

        recoil_presets = [
            ("🟢 خفيف (SMG)", 6.0, 0.0, 20.0),
            ("🔵 هجومي (AR)", 11.0, 1.0, 40.0),
            ("🟠 ثقيل (LMG)", 16.0, 2.0, 60.0),
            ("⚪ إيقاف", 0.0, 0.0, 0.0),
        ]
        for r_name, rv, rh, rd in recoil_presets:
            def _apply_r(v=rv, h=rh, d=rd):
                self.recoil_v_var.set(v)
                self._on_recoil_v_drag(v)
                self.recoil_h_var.set(h)
                self._on_recoil_h_drag(h)
                self.recoil_delay_var.set(d)
                self._on_recoil_delay_drag(d)

            ctk.CTkButton(
                rec_preset_bar, text=r_name, height=24,
                font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
                fg_color=CLR_INPUT_BG, hover_color=CLR_CARD_BORDER,
                border_width=1, border_color=CLR_ACCENT_BLUE,
                command=_apply_r
            ).pack(side="left", padx=2)

        self.lbl_recoil_v = ctk.CTkLabel(
            recoil_card, text=f"مقاومة الارتداد الرأسي (Vertical Pull): {self.recoil_v_var.get():.1f} px",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color=CLR_TEXT_WHITE,
            anchor="w"
        )
        self.lbl_recoil_v.pack(anchor="w", padx=10, pady=(2, 0))

        ctk.CTkSlider(
            recoil_card, from_=0.0, to=30.0, number_of_steps=60,
            variable=self.recoil_v_var, command=self._on_recoil_v_drag,
            progress_color=CLR_ACCENT_BLUE, button_color=CLR_ACCENT_CYAN,
            button_hover_color=CLR_ACCENT_HOVR, fg_color=CLR_CARD_BORDER
        ).pack(fill="x", padx=10, pady=(2, 6))

        self.lbl_recoil_h = ctk.CTkLabel(
            recoil_card, text=f"مقاومة الارتداد الأفقي (Horizontal Drift): {self.recoil_h_var.get():+.1f} px",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color=CLR_TEXT_WHITE,
            anchor="w"
        )
        self.lbl_recoil_h.pack(anchor="w", padx=10, pady=(2, 0))

        ctk.CTkSlider(
            recoil_card, from_=-15.0, to=15.0, number_of_steps=60,
            variable=self.recoil_h_var, command=self._on_recoil_h_drag,
            progress_color=CLR_ACCENT_CYAN, button_color=CLR_ACCENT_BLUE,
            button_hover_color=CLR_CYAN_HOVR, fg_color=CLR_CARD_BORDER
        ).pack(fill="x", padx=10, pady=(2, 6))

        # RECOIL DELAY
        self.lbl_recoil_delay = ctk.CTkLabel(
            recoil_card, text=f"تأخير بدء مانع الارتداد (Recoil Start Delay): {int(self.recoil_delay_var.get())} ms",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color=CLR_TEXT_WHITE,
            anchor="w"
        )
        self.lbl_recoil_delay.pack(anchor="w", padx=10, pady=(2, 0))

        ctk.CTkSlider(
            recoil_card, from_=0.0, to=200.0, number_of_steps=20,
            variable=self.recoil_delay_var, command=self._on_recoil_delay_drag,
            progress_color=CLR_ACCENT_CYAN, button_color=CLR_ACCENT_BLUE,
            button_hover_color=CLR_ACCENT_HOVR, fg_color=CLR_CARD_BORDER
        ).pack(fill="x", padx=10, pady=(2, 8))

        # بطاقة توجيهية لكيفية ضبط الارتداد
        info_card = self._make_card(f)
        self._card_header(info_card, "💡 دليل ضبط الارتداد التكتيكي", color=CLR_ACCENT_CYAN)

        tips = (
            "• السحب الرأسي (Vertical Pull): يعوض قفز فوهة السلاح لأعلى عند إطلاق النار المستمر.\n"
            "• الانجراف الأفقي (Horizontal Drift): يعوض ميلان الرصاص لليمين (+) أو لليسار (-).\n"
            "• تأخير البدء (Start Delay): يسمح للطلقة الأولى بالخروج بدقة قبل تطبيق السحب لمنع الإزاحة المبكرة."
        )
        ctk.CTkLabel(
            info_card, text=tips, justify="left",
            font=ctk.CTkFont(family="Segoe UI", size=10), text_color=CLR_TEXT_MUTED
        ).pack(anchor="w", padx=10, pady=6)

    # ═══════════════════════════════════════════════════════════════════════
    # التبويب 4: الرؤية والألوان والذكاء الاصطناعي (Vision & DirectML AI)
    # ═══════════════════════════════════════════════════════════════════════

    def _build_tab_vision_ai(self) -> None:
        f = ctk.CTkScrollableFrame(self.tab_container, fg_color=CLR_BG_DARK, corner_radius=0)
        self._tab_frames.append(f)
        self._add_tab_return_banner(f, "🎨 لوحة حساسية الألوان والذكاء الاصطناعي")

        card = self._make_card(f)
        self._card_header(card, "🎨 مساحة الألوان وحساسية الكشف (Color Space & Tolerance)", color=CLR_ACCENT_CYAN)

        self.lbl_tol = ctk.CTkLabel(
            card, text=f"حساسية اللون: ±{self.tolerance_var.get():.1f}",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color=CLR_TEXT_WHITE,
            anchor="w"
        )
        self.lbl_tol.pack(anchor="w", padx=10, pady=(3, 0))

        ctk.CTkSlider(
            card, from_=3.0, to=40.0, number_of_steps=74,
            variable=self.tolerance_var, command=self._on_tolerance_drag,
            progress_color=CLR_ACCENT_BLUE, button_color=CLR_ACCENT_CYAN,
            button_hover_color=CLR_ACCENT_HOVR, fg_color=CLR_CARD_BORDER
        ).pack(fill="x", padx=10, pady=(2, 6))

        self.lbl_max_area = ctk.CTkLabel(
            card, text=f"أقصى مساحة للهدف: {int(self.max_area_var.get())} بكسل²",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color=CLR_TEXT_WHITE,
            anchor="w"
        )
        self.lbl_max_area.pack(anchor="w", padx=10, pady=(2, 0))

        ctk.CTkSlider(
            card, from_=500.0, to=15000.0, number_of_steps=145,
            variable=self.max_area_var, command=self._on_max_area_drag,
            progress_color=CLR_ACCENT_BLUE, button_color=CLR_ACCENT_CYAN,
            button_hover_color=CLR_ACCENT_HOVR, fg_color=CLR_CARD_BORDER
        ).pack(fill="x", padx=10, pady=(2, 6))

        color_btn_row = ctk.CTkFrame(card, fg_color="transparent")
        color_btn_row.pack(fill="x", padx=10, pady=(2, 6))

        ctk.CTkButton(
            color_btn_row, text="🌸 ماجنتا كود (#FF00FF)",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            fg_color="#A21CAF", hover_color="#C026D3", text_color="#FFFFFF",
            corner_radius=6, height=26,
            command=lambda: self._set_color_preset("ff00ff")
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            color_btn_row, text="🔴 أحمر (#FF2D2D)",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            fg_color=CLR_INPUT_BG, hover_color=CLR_CARD_BORDER, text_color=CLR_DANGER_RED,
            border_width=1, border_color=CLR_CARD_BORDER, corner_radius=6, height=26,
            command=lambda: self._set_color_preset("ff2d2d")
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            color_btn_row, text="📖 دليل ضبط إعدادات اللعبة",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            fg_color=CLR_INPUT_BG, hover_color=CLR_ACCENT_BLUE, text_color=CLR_ACCENT_CYAN,
            border_width=1, border_color=CLR_CARD_BORDER, corner_radius=6, height=26,
            command=self._show_ingame_guide
        ).pack(side="left")

        ai_card = self._make_card(f)
        self._card_header(ai_card, "🤖 نماذج الذكاء الاصطناعي والتتبع الحركي (DirectML & AI Models)", color=CLR_ACCENT_CYAN)

        ctk.CTkSwitch(
            ai_card, text="🧠 الذكاء الاصطناعي المحلي المسرّع بـ DirectML (DirectX 12 على كرت الشاشة)",
            variable=self.local_ai_var, command=self._toggle_local_ai,
            progress_color=CLR_ACCENT_CYAN, font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold")
        ).pack(anchor="w", padx=10, pady=5)

        ctk.CTkSwitch(
            ai_card, text="نموذج التنبؤ الحركي بالذكاء الاصطناعي (تعويض بطء المعالجة)",
            variable=self.ai_var, command=self._on_ai_toggle,
            progress_color=CLR_ACCENT_CYAN, font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold")
        ).pack(anchor="w", padx=10, pady=5)

        ctk.CTkSwitch(
            ai_card, text="النقر التلقائي عند مطابقة الهدف [Auto-Click]",
            variable=self.auto_click_var, command=self._on_click_toggle,
            progress_color=CLR_ACCENT_CYAN, font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold")
        ).pack(anchor="w", padx=10, pady=5)

        ctk.CTkSwitch(
            ai_card, text="سير عمل Roboflow AI السحابي (كشف وتتبع لاعبي كود سحابياً)",
            variable=self.roboflow_ai_var, command=self._on_roboflow_toggle,
            progress_color=CLR_ACCENT_BLUE, font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold")
        ).pack(anchor="w", padx=10, pady=(5, 8))

        cap_card = self._make_card(f)
        self._card_header(cap_card, "⚡ محرك التقاط الشاشة المباشر (DirectX 11 DXGI 240Hz)", color=CLR_ACCENT_BLUE)

        ctk.CTkLabel(
            cap_card, text="اختر محرك الالتقاط وسرعة سحب الإطارات:",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color=CLR_TEXT_WHITE,
            anchor="w"
        ).pack(anchor="w", padx=10, pady=(4, 2))

        ctk.CTkSegmentedButton(
            cap_card,
            values=["تلقائي (DirectX 11 DXGI 240Hz)", "MSS القياسي (60Hz)"],
            command=self._on_capture_backend_change,
            selected_color=CLR_ACCENT_BLUE,
            selected_hover_color=CLR_ACCENT_CYAN,
        ).pack(fill="x", padx=10, pady=(2, 8))

    # ═══════════════════════════════════════════════════════════════════════
    # التبويب 5: بروفايلات الألعاب والأدوات (Game Profiles & Tools)
    # ═══════════════════════════════════════════════════════════════════════

    def _build_tab_game_profiles_tools(self) -> None:
        f = ctk.CTkScrollableFrame(self.tab_container, fg_color=CLR_BG_DARK, corner_radius=0)
        self._tab_frames.append(f)
        self._add_tab_return_banner(f, "🏆 لوحة بروفايلات الألعاب والأدوات التكتيكية")

        # ── 1. بطاقة بروفايلات الألعاب التنافسية (Game Profiles) ────────────
        gp_card = self._make_card(f)
        self._card_header(gp_card, "🏆 بروفايلات الألعاب التنافسية الجاهزة (Competitive Game Profiles)", color=CLR_ACCENT_CYAN)

        gp_row = ctk.CTkFrame(gp_card, fg_color="transparent")
        gp_row.pack(fill="x", padx=10, pady=(2, 6))

        ctk.CTkButton(
            gp_row, text="🎮 كود BO6 / BO7 (PS5)",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            fg_color=CLR_ACCENT_BLUE, hover_color=CLR_ACCENT_HOVR, text_color="#FFFFFF",
            corner_radius=6, height=28, command=lambda: self._apply_game_preset("COD_BO6_PS5")
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            gp_row, text="🎯 وارزون التكتيكي (Warzone)",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            fg_color=CLR_INPUT_BG, hover_color=CLR_ACCENT_CYAN, text_color=CLR_TEXT_WHITE,
            border_width=1, border_color=CLR_CARD_BORDER, corner_radius=6, height=28,
            command=lambda: self._apply_game_preset("WARZONE_TACTICAL")
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            gp_row, text="⚡ الخاطف التنافسي (Flick Beast)",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            fg_color=CLR_INPUT_BG, hover_color=CLR_DANGER_RED, text_color=CLR_TEXT_WHITE,
            border_width=1, border_color=CLR_CARD_BORDER, corner_radius=6, height=28,
            command=lambda: self._apply_game_preset("FLICK_BEAST")
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            gp_row, text="📖 دليل الإعدادات داخل اللعبة",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            fg_color=CLR_INPUT_BG, hover_color=CLR_ACCENT_BLUE, text_color=CLR_ACCENT_CYAN,
            border_width=1, border_color=CLR_CARD_BORDER, corner_radius=6, height=28,
            command=self._show_ingame_guide
        ).pack(side="left")

        # ── 2. بطاقة سوني فايف ريموت بلاي المدمج (PS5 Hub) ─────────────────
        ps5_card = self._make_card(f)
        self._card_header(ps5_card, "🎮 سوني فايف ريموت بلاي المدمج (PS5 DualSense & Remote Play Hub)", color="#0070D1")

        ps5_row = ctk.CTkFrame(ps5_card, fg_color="transparent")
        ps5_row.pack(fill="x", padx=10, pady=(2, 6))

        ctk.CTkButton(
            ps5_row, text="🚀 تشغيل Chiaki PS5 المدمج",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color="#0070D1", hover_color="#0056A3", text_color="#FFFFFF",
            corner_radius=6, height=32, command=self._launch_ps5_stream
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            ps5_row, text="⚡ ضبط الإعدادات المثالية (منع انزياح الألوان)",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            fg_color=CLR_INPUT_BG, hover_color=CLR_ACCENT_BLUE, text_color=CLR_ACCENT_CYAN,
            border_width=1, border_color=CLR_CARD_BORDER, corner_radius=6, height=32,
            command=self._apply_chiaki_optimal_settings
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            ps5_row, text="🔑 استخراج معرف PSN ID",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            fg_color=CLR_INPUT_BG, hover_color=CLR_ACCENT_HOVR, text_color=CLR_TEXT_MUTED,
            border_width=1, border_color=CLR_CARD_BORDER, corner_radius=6, height=32,
            command=open_psn_lookup_tool
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            ps5_row, text="🟢 تشغيل Xbox Remote Play",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            fg_color=CLR_INPUT_BG, hover_color="#107C10", text_color="#107C10",
            border_width=1, border_color=CLR_CARD_BORDER, corner_radius=6, height=32,
            command=self._launch_xbox_stream
        ).pack(side="left")

        self.lbl_ps5_status = ctk.CTkLabel(
            ps5_card, textvariable=self.ps5_status_var,
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            fg_color=CLR_INPUT_BG, text_color=CLR_SUCCESS_GRN,
            corner_radius=6, padx=10, pady=4
        )
        self.lbl_ps5_status.pack(anchor="w", padx=10, pady=(0, 6))

        # ── 3. بطاقة عزل يد التحكم الحقيقية (Nefarius HidHide) ────────────────
        hh_card = self._make_card(f)
        self._card_header(hh_card, "🛡️ عزل يد التحكم الحقيقية (Nefarius HidHide Cloaking Hub)", color=CLR_SUCCESS_GRN)

        self.lbl_hh_desc = ctk.CTkLabel(
            hh_card,
            text="عزل اليد الحقيقية يمنع Chiaki واللعبة من قراءة اليد الأصلية مباشرة لمنع تعارض الإدخال المزدوج.\nالتطبيق يمرر كافة الأزرار والعصي إلى اليد الافتراضية مع دمج زاوية التصويب التلقائي بسلاسة.",
            font=ctk.CTkFont(family="Segoe UI", size=10), text_color=CLR_TEXT_MUTED, justify="left"
        )
        self.lbl_hh_desc.pack(anchor="w", padx=10, pady=(2, 6))

        hh_btn_row = ctk.CTkFrame(hh_card, fg_color="transparent")
        hh_btn_row.pack(fill="x", padx=10, pady=(0, 6))

        ctk.CTkButton(
            hh_btn_row, text="🛡️ فتح برنامج HidHide الرسمي",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            fg_color=CLR_INPUT_BG, hover_color=CLR_CARD_BORDER, text_color=CLR_ACCENT_CYAN,
            border_width=1, border_color=CLR_CARD_BORDER, corner_radius=6, height=30,
            command=self._launch_hidhide_gui
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            hh_btn_row, text="✅ إضافة البوت للقائمة المسموحة",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            fg_color=CLR_INPUT_BG, hover_color=CLR_SUCCESS_GRN, text_color=CLR_SUCCESS_GRN,
            border_width=1, border_color=CLR_CARD_BORDER, corner_radius=6, height=30,
            command=self._whitelist_hidhide_app
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            hh_btn_row, text="🔒 تفعيل الحجب (Cloak On)",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            fg_color=CLR_ACCENT_BLUE, hover_color=CLR_ACCENT_HOVR, text_color="#FFFFFF",
            corner_radius=6, height=30,
            command=lambda: self._set_hidhide_cloak(True)
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            hh_btn_row, text="🔓 إلغاء الحجب (Cloak Off)",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            fg_color=CLR_INPUT_BG, hover_color=CLR_DANGER_RED, text_color=CLR_DANGER_RED,
            border_width=1, border_color=CLR_CARD_BORDER, corner_radius=6, height=30,
            command=lambda: self._set_hidhide_cloak(False)
        ).pack(side="left")

        # ── 3. بطاقة مقاييس الأداء والتحليلات الحية للرصد ──────────────────
        tc = self._make_card(f)
        self._card_header(tc, "📊 مقاييس الأداء والتحليلات الحية للرصد (Live Telemetry)", color=CLR_ACCENT_CYAN)

        self.telemetry_labels: dict[str, ctk.CTkLabel] = {}
        metrics = [
            ("معدل التحديث الحركي (FPS / Hz):", "hz", "--"),
            ("زمن المعالجة والاستجابة (Latency):", "latency", "-- ms"),
            ("حالة رصد الهدف:", "status", "جاهز"),
            ("إحداثيات الهدف الحالية (X, Y):", "pos", "(0, 0)"),
            ("النقطة المتوقعة بالذكاء (Pred X, Y):", "pred", "(0, 0)"),
            ("نصف قطر ومساحة الهدف:", "radius", "-- px"),
            ("نسبة الثقة بالرصد:", "conf", "-- %"),
            ("نافذة اللعبة المربوطة:", "window", "--"),
            ("حالة عزل اليد الحقيقية (HidHide):", "hidhide", "جاري الفحص..."),
        ]

        for title, key, init_val in metrics:
            row = ctk.CTkFrame(tc, fg_color=CLR_INPUT_BG, corner_radius=6)
            row.pack(fill="x", padx=10, pady=2)

            ctk.CTkLabel(
                row, text=title, font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
                text_color=CLR_TEXT_MUTED
            ).pack(side="left", padx=8, pady=4)

            lbl = ctk.CTkLabel(
                row, text=init_val, font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
                text_color=CLR_TEXT_WHITE
            )
            lbl.pack(side="right", padx=8, pady=4)
            self.telemetry_labels[key] = lbl

        # ── 4. بطاقة محاكي تدريب التصويب المدمج ─────────────────────────────
        launch_card = self._make_card(f)
        self._card_header(launch_card, "🎯 ساحات تدريب واختبار التصويب (3D & 2D)", color=CLR_ACCENT_BLUE)

        ctk.CTkButton(
            launch_card, text="🎮 تشغيل لعبة الساحة ثلاثية الأبعاد 3D FPS Arena [اختبار اليد والتتبع]", height=42,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color=CLR_ACCENT_BLUE, hover_color=CLR_ACCENT_HOVR,
            border_width=1, border_color=CLR_ACCENT_CYAN,
            command=self._launch_trainer_3d
        ).pack(fill="x", padx=10, pady=(4, 6))

        ctk.CTkButton(
            launch_card, text="🎯 تشغيل لعبة تدريب التصويب الثنائية 2D [Aim Trainer]", height=34,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color=CLR_INPUT_BG, hover_color=CLR_CARD_BORDER,
            border_width=1, border_color=CLR_CARD_BORDER,
            command=self._launch_trainer
        ).pack(fill="x", padx=10, pady=(2, 8))

    # التوافق مع النداءات القديمة
    _build_tab_main_hud = _build_tab_preview_stream
    _build_tab_controller = _build_tab_controller_input
    _build_tab_vision_tuning = _build_tab_vision_ai
    _build_tab_telemetry_robotics = _build_tab_game_profiles_tools

    # ── أدوات بناء البطاقات والعناوين ──────────────────────────────────────

    def _make_card(self, parent) -> ctk.CTkFrame:
        c = ctk.CTkFrame(parent, fg_color=CLR_CARD_BG, corner_radius=10, border_width=1, border_color=CLR_CARD_BORDER)
        c.pack(fill="x", padx=2, pady=4)
        return c

    def _card_header(self, parent, text: str, color: str = CLR_ACCENT_VIOL) -> None:
        ctk.CTkLabel(
            parent, text=text,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=color
        ).pack(anchor="w", padx=10, pady=(5, 3))

    # ── معالجة أحداث النقر على الشبكات التفاعلية ───────────────────────────

    def _select_intensity(self, name: str) -> None:
        self.intensity_var.set(name)
        self.cfg.intensity_profile = name
        prof = config.INTENSITY_PROFILES.get(name)
        if prof is not None:
            spd = float(prof["aim_speed"])
            smth = float(prof["smoothing"])
            fov = float(prof["fov_radius_px"])

            self.cfg.aim_speed = spd
            self.cfg.smoothing = smth
            self.cfg.fov_radius_px = fov

            self.aim_speed_var.set(spd)
            self.smoothing_var.set(smth)
            self.fov_radius_var.set(fov)

            if hasattr(self, "lbl_smooth_slider"):
                self.lbl_smooth_slider.configure(text=f"سلاسة التصويب: {smth:.2f}")
            if hasattr(self, "lbl_fov_slider"):
                self.lbl_fov_slider.configure(text=f"نطاق دائرة التصويب: {int(fov)} بكسل")

            if self.worker is not None:
                self.worker._color_detector.fov_radius = fov
                self.worker._smart_detector.fov_radius = fov

        self._refresh_intensity_cards()
        self.status_text.set(f"⚡ تم تفعيل نمط الشدة: {name}")

    def _refresh_intensity_cards(self) -> None:
        curr = self.intensity_var.get()
        for name, frame in self._intensity_cards.items():
            if name == curr:
                frame.configure(
                    border_color=CLR_ACCENT_VIOL, border_width=2,
                    fg_color=CLR_CARD_ACTIVE
                )
            else:
                frame.configure(
                    border_color=CLR_CARD_BORDER, border_width=1,
                    fg_color=CLR_INPUT_BG
                )

    def _select_target_priority(self, name: str) -> None:
        self.target_priority_var.set(name)
        self.cfg.target_priority = name
        self._refresh_target_cards()
        if name == "MARKER":
            self.vertical_offset_var.set(0.0)
            self.cfg.vertical_offset_px = 0.0
            self.status_text.set("🎯 أولوية الاستهداف: علامة اللاعب مباشرة بدون إزاحة")
        elif name == "HEAD":
            self.vertical_offset_var.set(15.0)
            self.cfg.vertical_offset_px = 15.0
            self.status_text.set("👤 أولوية الاستهداف: رأس اللاعب")
        elif name == "CHEST":
            self.vertical_offset_var.set(0.0)
            self.cfg.vertical_offset_px = 0.0
            self.status_text.set("🛡️ أولوية الاستهداف: صدر اللاعب")
        elif name == "RANDOM":
            self.status_text.set("🎲 أولوية الاستهداف: تباين بشري عشوائي")
        else:
            self.status_text.set(f"🎯 تم ضبط أولوية الاستهداف: {name}")

    def _refresh_target_cards(self) -> None:
        curr = self.target_priority_var.get()
        for name, frame in self._target_cards.items():
            if name == curr:
                frame.configure(
                    border_color=CLR_ACCENT_VIOL, border_width=2,
                    fg_color=CLR_CARD_ACTIVE
                )
            else:
                frame.configure(
                    border_color=CLR_CARD_BORDER, border_width=1,
                    fg_color=CLR_INPUT_BG
                )

    # ── معالجة أشرطة التمرير والمدخلات ─────────────────────────────────────

    def _on_fov_slider_drag(self, val: float) -> None:
        self._on_fov_radius_change(str(val))

    def _on_fov_radius_change(self, val: str) -> None:
        v = float(val)
        self.cfg.fov_radius_px = v
        if hasattr(self, "lbl_fov_slider"):
            self.lbl_fov_slider.configure(text=f"نطاق دائرة التصويب: {int(v)} بكسل")
        if self.worker is not None:
            self.worker._smart_detector.fov_radius = v
            self.worker._color_detector.fov_radius = v

    def _on_vertical_offset_drag(self, val: float) -> None:
        v = float(val)
        self.cfg.vertical_offset_px = v
        if hasattr(self, "lbl_offset_slider"):
            self.lbl_offset_slider.configure(text=f"الإزاحة الرأسية للرأس: {int(v)} بكسل")

    def _on_smooth_slider_drag(self, val: float) -> None:
        v = float(val)
        self.cfg.smoothing = v
        if hasattr(self, "lbl_smooth_slider"):
            self.lbl_smooth_slider.configure(text=f"سلاسة التصويب: {v:.2f}")

    def _on_stick_sens_drag(self, val: float) -> None:
        v = round(float(val), 2)
        self.cfg.stick_sensitivity = v
        self.cfg.controller_bindings["STICK_SENSITIVITY"] = v
        if hasattr(self, "lbl_sens"):
            self.lbl_sens.configure(text=f"حساسية عصا التحكم (STICK_SENSITIVITY): {v:.2f}x")
        self.cfg.save()

    def _on_stick_smoothing_drag(self, val: float) -> None:
        v = round(float(val), 2)
        self.cfg.stick_smoothing = v
        self.cfg.controller_bindings["STICK_SMOOTHING"] = v
        if hasattr(self, "lbl_stick_smooth"):
            self.lbl_stick_smooth.configure(text=f"تنعيم استجابة العصا (STICK_SMOOTHING): {v:.2f}")
        self.cfg.save()

    def _on_deadzone_drag(self, val: float) -> None:
        v = float(val)
        self.cfg.deadzone_px = v
        self.cfg.controller_bindings["DEADZONE_PX"] = v
        if hasattr(self, "lbl_deadzone"):
            self.lbl_deadzone.configure(text=f"منطقة الموت للأنالوج (DEADZONE_PX): {int(v)} بكسل")
        self.cfg.save()

    def _on_power_exponent_drag(self, val: float) -> None:
        v = round(float(val), 2)
        self.cfg.power_exponent = v
        if hasattr(self, "lbl_power_exp"):
            self.lbl_power_exp.configure(text=f"منحنى القوة اللاخطي (Power Curve Exponent): {v:.2f}")
        self.cfg.save()

    def _on_reversal_damp_drag(self, val: float) -> None:
        v = round(float(val), 2)
        self.cfg.reversal_damping = v
        if hasattr(self, "lbl_reversal_damp"):
            self.lbl_reversal_damp.configure(text=f"كبح الارتداد العكسي (Reversal Damping): {v:.2f}")
        self.cfg.save()

    def _on_stick_breakaway_drag(self, val: float) -> None:
        v = round(float(val), 2)
        self.cfg.stick_min_breakaway = v
        if hasattr(self, "lbl_breakaway"):
            self.lbl_breakaway.configure(text=f"دفعة كسر منطقة الموت (Anti-Deadzone Punch): {v:.2f}")
        self.cfg.save()

    def _on_trigger_thresh_drag(self, val: float) -> None:
        v = round(float(val), 2)
        self.cfg.trigger_threshold = v
        if hasattr(self, "lbl_trigger_thresh"):
            self.lbl_trigger_thresh.configure(text=f"عتبة استجابة زناد L2/R2 (Trigger Threshold): {int(v * 100)}%")
        self.cfg.save()

    def _on_head_bias_drag(self, val: float) -> None:
        v = round(float(val), 2)
        self.cfg.head_bias_percent = v
        if hasattr(self, "lbl_head_bias"):
            self.lbl_head_bias.configure(text=f"إزاحة الاستهداف نحو الرأس (Head-Bias Offset): {int(v * 100)}%")
        if self.worker is not None and hasattr(self.worker, "_local_ai") and self.worker._local_ai is not None:
            self.worker._local_ai.head_bias_percent = v
        self.cfg.save()

    def _on_recoil_delay_drag(self, val: float) -> None:
        v = float(val)
        self.cfg.recoil_delay_ms = v
        if hasattr(self, "lbl_recoil_delay"):
            self.lbl_recoil_delay.configure(text=f"تأخير بدء مانع الارتداد (Recoil Start Delay): {int(v)} ms")
        self.cfg.save()

    def _toggle_triggerbot(self) -> None:
        v = self.triggerbot_var.get()
        self.cfg.triggerbot_enabled = v
        if v:
            self.status_text.set("💥 تم تفعيل الإطلاق التلقائي [Triggerbot] عند محاذاة الهدف بالمنتصف")
        else:
            self.status_text.set("⚪ تم إيقاف الإطلاق التلقائي [Triggerbot]")
        self.cfg.save()

    def _on_controller_type_change(self, choice: str) -> None:
        is_ps = "PS5" in choice or "DualSense" in choice
        self.cfg.controller_type = "PS5" if is_ps else "XBOX"
        self.status_text.set(f"🎮 تم اختيار يد التحكم المصدرة: {choice}")
        self.cfg.save()

    def _toggle_static_rejection(self) -> None:
        self.cfg.static_prop_rejection = self.static_rejection_var.get()
        if self.worker is not None and hasattr(self.worker, "_smart_detector"):
            self.worker._smart_detector.static_prop_rejection = self.cfg.static_prop_rejection
        self.cfg.save()

    def _toggle_local_ai(self) -> None:
        self.cfg.use_local_ai = self.local_ai_var.get()
        if self.cfg.use_local_ai:
            self.status_text.set("🧠 تم تفعيل كاشف DirectML العصبي على كرت الشاشة (DirectX 12)")
        else:
            self.status_text.set("🎨 تم تفعيل كاشف الألوان السريع")
        self.cfg.save()

    def _on_capture_backend_change(self, choice: str) -> None:
        backend = "dxgi" if "DXGI" in choice else ("mss" if "MSS" in choice else "auto")
        self.cfg.capture_backend = backend
        if self.worker is not None and self.worker._capture is not None:
            self.worker._capture._backend = backend
            self.worker._capture._dxgi_failed = False
        self.status_text.set(f"⚡ تم تعيين محرك التقاط الشاشة: {choice}")
        self.cfg.save()

    def _on_tolerance_drag(self, val: float) -> None:
        self._on_tolerance_change(str(val))

    def _on_tolerance_change(self, val: str) -> None:
        v = float(val)
        self.cfg.color_tolerance_h = v
        if hasattr(self, "lbl_tol"):
            self.lbl_tol.configure(text=f"حساسية اللون: ±{v:.1f}")
        if self.worker is not None:
            self.worker._color_detector.tolerance_h = v
            self.worker._color_detector._ranges_cache = None
            self.worker._smart_detector.tolerance_h = v
            self.worker._smart_detector._ranges_cache = None

    def _on_max_area_drag(self, val: float) -> None:
        self._on_max_area_change(str(val))

    def _on_max_area_change(self, val: str) -> None:
        v = float(val)
        self.cfg.max_target_area_px = v
        if hasattr(self, "lbl_max_area"):
            self.lbl_max_area.configure(text=f"أقصى مساحة للهدف: {int(v)} بكسل²")
        if self.worker is not None:
            self.worker._smart_detector.max_area = v
            self.worker._color_detector.max_area = v

    def _on_auto_track_toggle(self) -> None:
        self.cfg.auto_track_enabled = self.auto_track_var.get()
        self.cfg.save()

    def _on_binding_change(self, key: str, val: str) -> None:
        if key in self.binding_vars:
            self.binding_vars[key].set(val)
        self.cfg.controller_bindings[key] = val
        if key == "AIM_TRIGGER":
            self.cfg.aim_trigger = val
        elif key == "FIRE_TRIGGER":
            self.cfg.fire_trigger = val
        self.status_text.set(f"🕹️ تم تحديث الزر: {key} -> {val}")
        self.cfg.save()

    def _listen_for_controller_bind(self, action_key: str, btn_widget: ctk.CTkButton) -> None:
        """الاستماع الحي لضغطة أي زر في يد التحكم وتعيينه فورياً للأمر المختار."""
        orig_text = "🎮 تعيين بالضغط"
        btn_widget.configure(text="🔴 اضغط الزر باليد...", fg_color="#F59E0B", text_color="#000000")

        start_time = time.time()
        timeout_sec = 6.0

        def _poll_input():
            if time.time() - start_time > timeout_sec:
                btn_widget.configure(text=orig_text, fg_color=CLR_CARD_BG, text_color=CLR_ACCENT_CYAN)
                return

            detected: str | None = None

            # 1. Direct Hardware Polling via Pygame for instant DualSense / PS4 recognition
            try:
                import pygame
                if not pygame.get_init():
                    pygame.init()
                if not pygame.joystick.get_init():
                    pygame.joystick.init()
                pygame.event.pump()
                if pygame.joystick.get_count() > 0:
                    js = pygame.joystick.Joystick(0)
                    if not js.get_init():
                        js.init()

                    # Check triggers (Axes 4 and 5)
                    num_axes = js.get_numaxes()
                    if num_axes >= 6:
                        lt_raw = js.get_axis(4)
                        rt_raw = js.get_axis(5)
                        if lt_raw > 0.20:
                            detected = "L2"
                        elif rt_raw > 0.20:
                            detected = "R2"

                    # Check buttons
                    if detected is None:
                        num_btns = js.get_numbuttons()
                        btn_names = {
                            0: "Cross",
                            1: "Circle",
                            2: "Square",
                            3: "Triangle",
                            4: "L1",
                            5: "R1",
                            6: "L2",
                            7: "R2",
                            8: "Share",
                            9: "Options",
                            10: "L3",
                            11: "R3",
                            12: "PS",
                            13: "Touchpad",
                        }
                        for b_i in range(num_btns):
                            if js.get_button(b_i):
                                detected = btn_names.get(b_i, f"Btn_{b_i}")
                                break

                    # Check D-Pad
                    if detected is None and js.get_numhats() > 0:
                        hx, hy = js.get_hat(0)
                        if hy == 1: detected = "DPAD_UP"
                        elif hy == -1: detected = "DPAD_DOWN"
                        elif hx == -1: detected = "DPAD_LEFT"
                        elif hx == 1: detected = "DPAD_RIGHT"
            except Exception:
                pass

            # 2. Fallback to GamepadManager
            if detected is None:
                if self.worker is not None:
                    gp = self.worker.get_gamepad_state()
                else:
                    try:
                        from bot.gamepad import GamepadManager
                        gp = GamepadManager().poll()
                    except Exception:
                        gp = None

                if gp and gp.connected:
                    if gp.left_trigger >= 0.25: detected = "L2"
                    elif gp.right_trigger >= 0.25: detected = "R2"
                    elif gp.buttons & 0x0100: detected = "L1"
                    elif gp.buttons & 0x0200: detected = "R1"
                    elif gp.buttons & 0x0080: detected = "R3"
                    elif gp.buttons & 0x0040: detected = "L3"
                    elif gp.buttons & 0x1000: detected = "Cross"
                    elif gp.buttons & 0x2000: detected = "Circle"
                    elif gp.buttons & 0x4000: detected = "Square"
                    elif gp.buttons & 0x8000: detected = "Triangle"
                    elif gp.buttons & 0x0001: detected = "DPAD_UP"
                    elif gp.buttons & 0x0002: detected = "DPAD_DOWN"
                    elif gp.buttons & 0x0004: detected = "DPAD_LEFT"
                    elif gp.buttons & 0x0008: detected = "DPAD_RIGHT"

            if detected:
                self._on_binding_change(action_key, detected)
                btn_widget.configure(text=f"✔ تم: {detected}", fg_color=CLR_SUCCESS_GRN, text_color="#FFFFFF")
                self.root.after(1400, lambda: btn_widget.configure(text=orig_text, fg_color=CLR_CARD_BG, text_color=CLR_ACCENT_CYAN))
                return

            self.root.after(25, _poll_input)

        self.root.after(25, _poll_input)

    def _apply_controller_preset(self, preset: dict[str, str]) -> None:
        for k, v in preset.items():
            if k in self.binding_vars:
                self.binding_vars[k].set(v)
                self.cfg.controller_bindings[k] = v
                if k == "AIM_TRIGGER":
                    self.cfg.aim_trigger = v
                elif k == "FIRE_TRIGGER":
                    self.cfg.fire_trigger = v
        self.cfg.save()
        self.status_text.set("🎮 تم تطبيق وحفظ التخطيط الجاهز ليد التحكم")

    def _on_recoil_v_drag(self, val: float) -> None:
        v = round(float(val), 1)
        self.cfg.recoil_vertical_px = v
        if hasattr(self, "lbl_recoil_v"):
            self.lbl_recoil_v.configure(text=f"مقاومة الارتداد الرأسي (Vertical Pull): {v:.1f} px")
        self.cfg.save()

    def _on_recoil_h_drag(self, val: float) -> None:
        v = round(float(val), 1)
        self.cfg.recoil_horizontal_px = v
        if hasattr(self, "lbl_recoil_h"):
            self.lbl_recoil_h.configure(text=f"مقاومة الارتداد الأفقي (Horizontal Drift): {v:+.1f} px")
        self.cfg.save()

    def _apply_game_preset(self, preset_key: str) -> None:
        if preset_key not in config.GAME_PRESETS:
            return
        p = config.GAME_PRESETS[preset_key]
        stick_sens = float(p.get("stick_sens", p.get("stick_sensitivity", 1.85)))
        stick_smooth = float(p.get("stick_smooth", p.get("stick_smoothing", 0.20)))
        power_exp = float(p.get("power_exponent", 1.15))
        reversal_damp = float(p.get("reversal_damping", 0.35))
        recoil_v = float(p.get("recoil_v", p.get("recoil_vertical_px", 0.0)))
        recoil_h = float(p.get("recoil_h", p.get("recoil_horizontal_px", 0.0)))

        self.stick_sens_var.set(stick_sens)
        self.stick_smooth_var.set(stick_smooth)
        self.power_exponent_var.set(power_exp)
        self.reversal_damp_var.set(reversal_damp)
        self.recoil_v_var.set(recoil_v)
        self.recoil_h_var.set(recoil_h)

        breakaway = float(p.get("stick_min_breakaway", 0.08))
        self.stick_breakaway_var.set(breakaway)
        self.cfg.stick_min_breakaway = breakaway

        self.cfg.stick_sensitivity = stick_sens
        self.cfg.stick_smoothing = stick_smooth
        self.cfg.power_exponent = power_exp
        self.cfg.reversal_damping = reversal_damp
        self.cfg.recoil_vertical_px = recoil_v
        self.cfg.recoil_horizontal_px = recoil_h

        bindings = p.get("bindings", {})
        for k, v in bindings.items():
            if k in self.binding_vars:
                self.binding_vars[k].set(v)
                self.cfg.controller_bindings[k] = v
                if k == "AIM_TRIGGER":
                    self.cfg.aim_trigger = v
                elif k == "FIRE_TRIGGER":
                    self.cfg.fire_trigger = v

        if hasattr(self, "lbl_sens"):
            self.lbl_sens.configure(text=f"حساسية عصا التحكم (STICK_SENSITIVITY): {stick_sens:.2f}x")
        if hasattr(self, "lbl_stick_smooth"):
            self.lbl_stick_smooth.configure(text=f"تنعيم استجابة العصا (STICK_SMOOTHING): {stick_smooth:.2f}")
        if hasattr(self, "lbl_power_exp"):
            self.lbl_power_exp.configure(text=f"منحنى القوة اللاخطي (Power Curve Exponent): {power_exp:.2f}")
        if hasattr(self, "lbl_reversal_damp"):
            self.lbl_reversal_damp.configure(text=f"كبح الارتداد العكسي (Reversal Damping): {reversal_damp:.2f}")
        if hasattr(self, "lbl_breakaway"):
            self.lbl_breakaway.configure(text=f"دفعة كسر منطقة الموت (Anti-Deadzone Punch): {breakaway:.2f}")
        if hasattr(self, "lbl_recoil_v"):
            self.lbl_recoil_v.configure(text=f"مقاومة الارتداد الرأسي: {recoil_v:.1f} px")
        if hasattr(self, "lbl_recoil_h"):
            self.lbl_recoil_h.configure(text=f"مقاومة الارتداد الأفقي: {recoil_h:+.1f} px")

        if "target_color" in p:
            rgb = p["target_color"]
            self.cfg.target_color = rgb
            self._tracked_color = rgb
            h = rgb_to_hex(rgb)
            if hasattr(self, "color_entry_var"):
                self.color_entry_var.set(h.lstrip("#"))
            if hasattr(self, "color_swatch"):
                self.color_swatch.config(bg=h)
            if self.worker is not None:
                self.worker._color_detector.color = rgb
                self.worker._color_detector._ranges_cache = None
                self.worker._smart_detector.color = rgb
                self.worker._smart_detector._ranges_cache = None

        self.cfg.save()
        self.status_text.set(f"🏆 تم تطبيق بروفايل اللعبة: {p['name']}")

    def _launch_ps5_stream(self) -> None:
        proc = launch_ps5_client()
        if proc:
            self.ps5_status_var.set("🚀 تم تشغيل Chiaki PS5 بنجاح — جاري البحث والربط التلقائي...")
            self.status_text.set("🚀 تم تشغيل مشغل PS5 المدمج — جاري ربط الشاشة...")
            self.root.after(2500, self.auto_detect_chiaki)
        else:
            self.ps5_status_var.set("⚠️ تعذر تشغيل مشغل Chiaki PS5")
            self.status_text.set("⚠️ تأكد من وجود remote_play/ps5/lu.exe")

    def _launch_xbox_stream(self) -> None:
        proc = launch_xbox_client()
        if proc:
            self.ps5_status_var.set("🟢 تم تشغيل Greenlight Xbox بنجاح — جاري البحث والربط...")
            self.status_text.set("🟢 تم تشغيل مشغل Xbox المدمج — جاري ربط الشاشة...")
            self.root.after(3000, self.auto_detect_chiaki)
        else:
            self.ps5_status_var.set("⚠️ تعذر تشغيل مشغل Greenlight Xbox")
            self.status_text.set("⚠️ تأكد من وجود remote_play/xbox/xlu.exe")

    def _apply_chiaki_optimal_settings(self) -> None:
        ok = optimize_chiaki_settings()
        if ok:
            self.ps5_status_var.set("✅ تم حفظ إعدادات D3D11VA + H.264 بالريجستري (منع انزياح الألوان)")
            self.status_text.set("⚡ تم تطبيق أفضل إعدادات فك التشفير والأداء بدون انزياح ألوان")
            try:
                messagebox.showinfo("إعدادات Chiaki المثالية", "تم بنجاح تحديث إعدادات مشغل البث Chiaki في ريجستري الويندوز (D3D11VA + H.264 60FPS 1080p) لضمان أقصى سرعة واستقرار كامل للألوان دون أي انزياح.")
            except Exception:
                pass
        else:
            self.ps5_status_var.set("⚠️ تعذر تحديث إعدادات الريجستري لـ Chiaki")

    def _show_ingame_guide(self) -> None:
        """Display comprehensive in-game interface and remote play optimization guide."""
        dlg = ctk.CTkToplevel(self.root)
        dlg.title("📖 دليل ضبط إعدادات كود وسوني داخل اللعبة (In-Game Setup Guide)")
        dlg.geometry("660x540")
        dlg.configure(fg_color=CLR_BG_DARK)
        dlg.transient(self.root)

        scroll = ctk.CTkScrollableFrame(dlg, fg_color=CLR_BG_DARK, corner_radius=0)
        scroll.pack(fill="both", expand=True, padx=12, pady=12)

        ctk.CTkLabel(
            scroll, text="🎯 دليل ضبط الألوان والواجهة لأقصى أداء ورصد فوري",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color=CLR_ACCENT_CYAN, anchor="w"
        ).pack(fill="x", pady=(0, 10))

        c1 = self._make_card(scroll)
        self._card_header(c1, "🎮 1. إعدادات كود (Call of Duty: BO6 / Warzone / MW3)", color=CLR_ACCENT_BLUE)
        t1 = (
            "• تخصيص الألوان (Color Customization):\n"
            "  1. ادخل إلى الإعدادات (Settings) -> الواجهة (Interface) -> تخصيص الألوان (Color Customization).\n"
            "  2. اختر فلتر الألوان: Filter 2 (فلتر 2).\n"
            "  3. هدف فلتر الألوان: Both (العالم + الواجهة).\n"
            "  4. غيّر لون الأعداء (Enemies) إلى: الماجنتا / الوردي الفاقع (#FF00FF / Magenta).\n"
            "• أشرطة صحة الأعداء وأسماؤهم:\n"
            "  - فعّل ظهور أشرطة صحة الأعداء (Enemy Health Bars: ON).\n"
            "  - اضبط أسماء الأعداء (Enemy Nameplates) على: Full أو Abbreviated.\n"
            "  * ميزة هذا الضبط: شريط الصحة يظهر باللون الوردي فوق رأس العدو فور رؤيته مما يمنحك قفلاً بصرياً لحظياً!\n"
            "• حساسية اليد ومنطقة الموت:\n"
            "  - حساسية المحاور: 6-8 | منحنى الاستجابة (Response Curve): Dynamic (ديناميكي).\n"
            "  - الحد الأدنى لمنطقة الموت (Min Deadzone): 0.03 - 0.05 لسرعة استجابة خارقة."
        )
        ctk.CTkLabel(
            c1, text=t1, justify="left", font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=CLR_TEXT_WHITE
        ).pack(anchor="w", padx=10, pady=8)

        c2 = self._make_card(scroll)
        self._card_header(c2, "📺 2. إعدادات بث سوني (Chiaki PS5 / Xbox Remote Play)", color="#0070D1")
        t2 = (
            "• الدقة ومعدل الإطارات: 1080p بمعدل 60 إطار في الثانية (60 FPS).\n"
            "• معدل البت (Bitrate): 20000 - 30000 kbps لسلاسة الصورة وتقليل التشويش.\n"
            "• محرك فك التشفير: D3D11 Hardware Acceleration (تسريع عتادي).\n"
            "• كتم ألوان الريموت بلاي: اضغط على زر '⚡ ضبط الإعدادات المثالية' في تبويب بروفايلات الألعاب لمنع انزياح الألوان."
        )
        ctk.CTkLabel(
            c2, text=t2, justify="left", font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=CLR_TEXT_WHITE
        ).pack(anchor="w", padx=10, pady=8)

        c3 = self._make_card(scroll)
        self._card_header(c3, "🛡️ 3. عزل يد التحكم الحقيقية (Nefarius HidHide)", color=CLR_SUCCESS_GRN)
        t3 = (
            "• فائدة العزل: يمنع Chiaki أو اللعبة من قراءة اليد الحقيقية مباشرة لتفادي تعارض الإدخال المزدوج.\n"
            "• تمرير اليد التلقائي (Full Pass-Through): التطبيق يقوم بقراءة اليد الحقيقية وتمرير كافة حركاتها وأزرارها\n"
            "  إلى اليد الافتراضية مع دمج التصويب المساعد تلقائياً دون أي شعور بالتأخير.\n"
            "• خطوات التفعيل السريع:\n"
            "  1. اضغط '✅ إضافة البوت للقائمة المسموحة' لمنح البوت إمكانية قراءة اليد.\n"
            "  2. اضغط '🔒 تفعيل الحجب (Cloak On)' لحجب اليد الحقيقية عن باقي التطبيقات."
        )
        ctk.CTkLabel(
            c3, text=t3, justify="left", font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=CLR_TEXT_WHITE
        ).pack(anchor="w", padx=10, pady=8)

        ctk.CTkButton(
            scroll, text="إغلاق الدليل", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color=CLR_ACCENT_BLUE, hover_color=CLR_ACCENT_HOVR, text_color="#FFFFFF",
            corner_radius=6, height=32, command=dlg.destroy
        ).pack(pady=(4, 10))

    def _launch_hidhide_gui(self) -> None:
        """Launch the official Nefarius HidHide configuration client."""
        if self.hidhide_mgr.is_gui_installed:
            ok = self.hidhide_mgr.launch_gui()
            if ok:
                self.status_text.set("🛡️ تم فتح لوحة تحكم HidHide الرسمية")
            else:
                self.status_text.set("⚠️ تعذر فتح لوحة HidHide (يرجى قبول إذن المسؤول UAC)")
        else:
            messagebox.showinfo("HidHide", "واجهة HidHideClient غير موجودة في المسار القياسي.")

    def _whitelist_hidhide_app(self) -> None:
        """Add current app and python executable to HidHide whitelist with elevation."""
        if not self.hidhide_mgr.is_installed:
            messagebox.showwarning("HidHide", "برنامج HidHide غير مثبت على النظام.")
            return
        ok = self.hidhide_mgr.whitelist_current_process_elevated()
        if ok:
            self.status_text.set("✅ تم إرسال طلب إضافة البوت للقائمة المسموحة في HidHide")
        else:
            self.status_text.set("⚠️ تم إلغاء طلب صلاحية المسؤول أو تعذر التسجيل")

    def _set_hidhide_cloak(self, enable: bool) -> None:
        """Enable or disable HidHide cloaking with elevation."""
        if not self.hidhide_mgr.is_installed:
            messagebox.showwarning("HidHide", "برنامج HidHide غير مثبت على النظام.")
            return
        ok = self.hidhide_mgr.set_cloaking_elevated(enable)
        if ok:
            txt = "🔒 تم تفعيل حجب اليد الحقيقية" if enable else "🔓 تم إلغاء حجب اليد الحقيقية"
            self.status_text.set(txt)
        else:
            self.status_text.set("⚠️ تم إلغاء طلب صلاحية المسؤول أو تعذر تعديل الحجب")

    # ── إدارة الألوان وقطارة الشاشة ────────────────────────────────────────

    def _apply_color(self) -> None:
        rgb = hex_to_rgb(self.color_entry_var.get())
        if rgb is None:
            return
        self._tracked_color = rgb
        self.cfg.target_color = rgb
        if self.worker is not None:
            self.worker._color_detector.color = rgb
            self.worker._color_detector._ranges_cache = None
            self.worker._smart_detector.color = rgb
            self.worker._smart_detector._ranges_cache = None
        h = rgb_to_hex(rgb)
        self.color_entry_var.set(h.lstrip("#"))
        self.color_swatch.config(bg=h)
        self.status_text.set(f"✅ تم تطبيق لون الهدف بنجاح: {h}")

    def _set_color_preset(self, hv: str) -> None:
        self.color_entry_var.set(hv)
        self._apply_color()

    def _toggle_eyedropper(self) -> None:
        self._eyedropper_active = not self._eyedropper_active
        if self._eyedropper_active:
            self.btn_eyedropper.configure(fg_color=CLR_SUCCESS_GRN, text="🎯 القطارة نشطة [Space]")
            self.status_text.set("🎯 قطارة الشاشة نشطة: وجّه الماوس على الهدف واضغط مفتاح Space للالتقاط")
        else:
            self.btn_eyedropper.configure(fg_color=CLR_INPUT_BG, text="🎯 قطارة الشاشة [Space]")

    def _on_space_pressed(self, event=None) -> None:
        if not self._eyedropper_active:
            return
        rgb = get_pixel_at_cursor()
        if rgb is not None:
            h = rgb_to_hex(rgb)
            self.color_entry_var.set(h.lstrip("#"))
            self._apply_color()
            self._toggle_eyedropper()

    # ── تشغيل/إيقاف البوت ونمط الإدخال ─────────────────────────────────────

    def toggle_bot(self) -> None:
        self.cfg.bot_enabled = not self.cfg.bot_enabled
        if self.cfg.bot_enabled:
            self.preview_var.set(False)
            self._active_preview_only = False
            if self.worker is not None:
                self.worker.set_preview_only(False)
        else:
            self.preview_var.set(True)
            self._active_preview_only = True
            if self.worker is not None:
                self.worker.set_preview_only(True)
        self._refresh_toggle_btn()

    def _refresh_toggle_btn(self) -> None:
        if self.cfg.bot_enabled:
            self.btn_main_toggle.configure(text="🛑 إيقاف بوت التصويب [F6]", fg_color=CLR_DANGER_RED, hover_color="#DC2626")
            self.badge_status_var.set("● نشط")
            self.status_text.set("⚡ البوت نشط الآن — يعمل الرصد والتصويب التفاعلي")
        else:
            self.btn_main_toggle.configure(text="⚡ تشغيل بوت التصويب [F6]", fg_color=CLR_ACCENT_PURP, hover_color=CLR_ACCENT_HOVR)
            self.badge_status_var.set("○ جاهز")
            self.status_text.set("وضع المعاينة الآمن نشط — لا يتم إرسال نقرات أو تحريك للماوس")

        if self._mini_hud is not None:
            self._mini_hud.update_status(self.cfg.bot_enabled)

    def _on_preview_toggle(self) -> None:
        is_preview = self.preview_var.get()
        self._active_preview_only = is_preview
        if self.worker is not None:
            self.worker.set_preview_only(is_preview)
        if is_preview:
            self.cfg.bot_enabled = False
            self._refresh_toggle_btn()

    def _on_disable_mouse_toggle(self) -> None:
        v = self.disable_mouse_var.get()
        self.cfg.disable_mouse_movement = v
        if v:
            self.status_text.set("🛡️ تم حظر تحريك ماوس اللاب — البرنامج يعمل برصد وقفل بصري فقط دون لمس مؤشر الماوس")
        else:
            self.status_text.set("🖱️ تم تفعيل حركة الماوس")

    def _on_input_mode_change(self) -> None:
        is_ctrl = (self.input_mode_var.get() == "controller")
        self.controller_mode_var.set(is_ctrl)
        self.cfg.controller_mode = is_ctrl
        self.cfg.input_mode = "vgamepad" if is_ctrl else "sendinput"
        if is_ctrl:
            self.status_text.set("🎮 وضع يد التحكم الافتراضية (vgamepad) نشط — لا يتم تحريك مؤشر الماوس على سطح المكتب")
        else:
            self.cfg.disable_mouse_movement = False
            self.disable_mouse_var.set(False)
            self.status_text.set("🎯 نمط الماوس (SendInput) نشط — تم تفعيل تحريك المؤشر تلقائياً")

    def _on_ai_toggle(self) -> None:
        self.cfg.ai_assistant = self.ai_var.get()

    def _on_click_toggle(self) -> None:
        self.cfg.click_cooldown_ms = 120.0 if self.auto_click_var.get() else 999999.0

    def _on_roboflow_toggle(self) -> None:
        self.cfg.use_roboflow_ai = self.roboflow_ai_var.get()

    # ── ربط النوافذ وتطبيق Chiaki الآمن ────────────────────────────────────

    def auto_detect_chiaki(self) -> bool:
        self.src_mode.set(self.SRC_WINDOW)
        self._active_src_mode = self.SRC_WINDOW
        candidates = ["chiaki", "chiaki-ng", "ps remote play", "remote play", "playstation", "greenlight", "xbox"]
        info = find_window_info(candidates)
        if info is not None:
            matched_title, region = info
            self._window_title = matched_title
            self.lbl_win_status.configure(
                text=f"✅ مربوط بـ Chiaki: \"{matched_title}\" — {region.width}×{region.height} px",
                text_color=CLR_SUCCESS_GRN
            )
            self.chiaki_hud_var.set(f"🎮 Chiaki: {region.width}×{region.height}")
            self.status_text.set(f"✅ تم ربط نافذة Chiaki بنجاح ({matched_title})")
            self._init_worker()
            return True
        else:
            self._window_title = ""
            self.src_mode.set(self.SRC_WINDOW)
            self._active_src_mode = self.SRC_WINDOW
            self.lbl_win_status.configure(
                text="🔍 لم يتم العثور على Chiaki — تم تفعيل الرصد على وسط الشاشة [FOV]",
                text_color="#F59E0B"
            )
            self.chiaki_hud_var.set("🔍 بانتظار تشغيل Chiaki")
            self.status_text.set("🔍 لم يتم العثور على نافذة Chiaki مفتوحة — يعمل الرصد التلقائي مؤقتاً على وسط الشاشة دون توقف")
            self._init_worker()
            return False

    def _show_window_picker(self) -> None:
        popup = tk.Toplevel(self.root)
        popup.title("اختر نافذة اللعبة للربط")
        popup.geometry("450x360")
        popup.configure(bg=CLR_CARD_BG)
        popup.attributes("-topmost", True)

        tk.Label(
            popup, text="اختر نافذة اللعبة / البث من القائمة:",
            font=("Segoe UI", 10, "bold"), fg=CLR_TEXT_WHITE, bg=CLR_CARD_BG
        ).pack(anchor="w", padx=12, pady=(10, 4))

        lb = tk.Listbox(
            popup, bg=CLR_INPUT_BG, fg=CLR_TEXT_WHITE,
            selectbackground=CLR_ACCENT_PURP, font=("Segoe UI", 9), bd=0
        )
        lb.pack(fill="both", expand=True, padx=12, pady=4)

        wins = list_visible_windows()
        win_list = [(hwnd, title) for hwnd, title in wins if title != self.root.title()]

        def _is_priority(t: str) -> bool:
            tl = t.lower()
            return any(k in tl for k in ("chiaki", "remote play", "playstation"))

        ordered_wins = sorted(win_list, key=lambda w: not _is_priority(w[1]))
        for _, title in ordered_wins:
            prefix = "🎮 [CHIAKI] " if _is_priority(title) else "  "
            lb.insert("end", f"{prefix}{title}")

        def _pick():
            sel = lb.curselection()
            if not sel:
                return
            _, title = ordered_wins[sel[0]]
            popup.destroy()
            self._window_title = title
            self.src_mode.set(self.SRC_WINDOW)
            self._active_src_mode = self.SRC_WINDOW
            self.lbl_win_status.configure(text=f"🎯 النافذة المربوطة: {title}", text_color=CLR_SUCCESS_GRN)
            self._init_worker()

        tk.Button(
            popup, text="✔ ربط بالنافذة المحددة", font=("Segoe UI", 9, "bold"),
            bg=CLR_ACCENT_PURP, fg="#fff", bd=0, padx=12, pady=5, cursor="hand2", command=_pick
        ).pack(pady=8)

    # ── التحديث الدوري للمعاينة والمقاييس ─────────────────────────────────

    def _update_preview_feed(self) -> None:
        if not self._hotkey_running:
            return

        if self.worker is not None:
            try:
                canv_w = 840
                canv_h = 440
                if hasattr(self, "preview_canvas_box"):
                    w = self.preview_canvas_box.winfo_width()
                    h = self.preview_canvas_box.winfo_height()
                    if w > 100 and h > 100:
                        canv_w = min(1280, max(400, w - 8))
                        canv_h = min(720, max(250, h - 8))

                png_bytes = self.worker.get_latest_preview_png(max_width=canv_w, max_height=canv_h)
                if png_bytes:
                    photo = tk.PhotoImage(data=png_bytes)
                    self.preview_display_label.config(image=photo, text="", height=0)
                    self._preview_photo = photo
                    if self._mini_hud is not None:
                        self._mini_hud.update_frame(photo)
            except Exception:
                pass

        self.root.after(45, self._update_preview_feed)

    def _update_status_ui(self) -> None:
        if not self._hotkey_running:
            return

        if self.worker is not None:
            hz = round(self.worker._loop_hz, 1)
            lat = round(self.worker._last_latency_ms, 1)
            self.badge_fps_var.set(f"{hz} FPS")
            self.badge_latency_var.set(f"{lat} ms")

            # مقاييس يد التحكم
            gp = self.worker.get_gamepad_state()
            if gp.connected:
                aim_btn = self.cfg.controller_bindings.get("AIM_TRIGGER", "L1")
                self.badge_controller_var.set(f"🎮 {gp.device_name[:12]}")
                aim_tag = f" [{aim_btn}: نشط]" if gp.is_aiming else ""
                self.controller_hud_var.set(
                    f"🎮 {gp.device_name} | {aim_btn}: {'مضغوط' if gp.is_aiming else 'غير مضغوط'} | LT:{int(gp.left_trigger*100)}% RT:{int(gp.right_trigger*100)}%{aim_tag}"
                )
            else:
                self.badge_controller_var.set("🎮 يد غير متصلة بالـ PC")
                self.controller_hud_var.set("🎮 غير متصلة بالكمبيوتر — يعمل التتبع المستمر مباشرة مع الكونسول")

            # تحديث رادار الاستهداف
            det = self.worker.get_latest_detection()
            if det is not None:
                conf_val = getattr(det, "confidence", 1.0)
                conf_pct = int(conf_val * 100) if conf_val is not None else 100
                if hasattr(self, "lbl_radar_target"):
                    self.lbl_radar_target.configure(
                        text=f"🎯 تم قفل الهدف عند: ({det.x:.0f}, {det.y:.0f}) | الثقة: {conf_pct}% | الحجم: {det.radius:.0f}px",
                        text_color=CLR_SUCCESS_GRN
                    )
            else:
                if hasattr(self, "lbl_radar_target"):
                    self.lbl_radar_target.configure(
                        text="حالة الهدف: جاهز — بانتظار ظهور لون الهدف داخل دائرة التصويب",
                        text_color=CLR_TEXT_MUTED
                    )

            # تحديث تبويب المقاييس
            if hasattr(self, "telemetry_labels") and self.telemetry_labels:
                self.telemetry_labels["hz"].configure(text=f"{hz:.1f} Hz")
                self.telemetry_labels["latency"].configure(text=f"{lat:.1f} ms")

                if det is not None:
                    self.telemetry_labels["status"].configure(text="🎯 هدف مقفول ومحدد", text_color=CLR_SUCCESS_GRN)
                    self.telemetry_labels["pos"].configure(text=f"({det.x:.1f}, {det.y:.1f})")
                    pred_pt = getattr(self.worker._debug_snapshot, "aim_point", None)
                    if pred_pt:
                        self.telemetry_labels["pred"].configure(text=f"({pred_pt[0]:.1f}, {pred_pt[1]:.1f})")
                    self.telemetry_labels["radius"].configure(text=f"{det.radius:.1f} px ({det.area:.0f} px²)")
                    conf_val = getattr(det, "confidence", 1.0)
                    self.telemetry_labels["conf"].configure(text=f"{conf_val * 100:.1f} %")
                else:
                    self.telemetry_labels["status"].configure(text="○ جاهز", text_color=CLR_TEXT_MUTED)

                win_title = self._window_title if (self.src_mode.get() == self.SRC_WINDOW and self._window_title) else "وسط الشاشة (FOV)"
                self.telemetry_labels["window"].configure(text=win_title)

                if "hidhide" in self.telemetry_labels:
                    st = self.hidhide_mgr.get_status()
                    color = CLR_SUCCESS_GRN if st.get("cloaked") else (CLR_ACCENT_CYAN if st.get("installed") else CLR_TEXT_MUTED)
                    self.telemetry_labels["hidhide"].configure(text=st["message"], text_color=color)

        self.root.after(350, self._update_status_ui)

    def open_mini_hud(self) -> None:
        if self._mini_hud is None:
            self._mini_hud = MiniFloatingHUD(self)
            self.root.iconify()

    def _hotkey_listener(self) -> None:
        user32 = ctypes.windll.user32
        last_f6_pressed = False
        while self._hotkey_running:
            try:
                pressed = bool(user32.GetAsyncKeyState(VK_F6) & 0x8000)
                if pressed and not last_f6_pressed:
                    self.root.after(0, self.toggle_bot)
                last_f6_pressed = pressed
            except Exception:
                pass
            time.sleep(0.04)

    def _launch_trainer(self) -> None:
        try:
            subprocess.Popen([sys.executable, str(PROJECT_ROOT / "main.py")])
        except Exception as exc:
            messagebox.showerror("خطأ", f"تعذر فتح نافذة التدريب: {exc}")

    def _launch_trainer_3d(self) -> None:
        try:
            subprocess.Popen([sys.executable, str(PROJECT_ROOT / "game_3d.py")])
        except Exception as exc:
            messagebox.showerror("خطأ", f"تعذر فتح ساحة الأبعاد الثلاثية 3D: {exc}")

    def _on_close(self) -> None:
        self._hotkey_running = False
        if self.worker is not None:
            self.worker.stop()
        try:
            self.cfg.bot_enabled = False
            self.cfg.save()
        except Exception:
            pass
        self.root.destroy()


def main() -> None:
    root = ctk.CTk()
    AimBotDesktopApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
