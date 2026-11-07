# Project Handoff Documentation

## 1. Goal
The primary objective of this project is to develop a high-performance, responsive computer vision and controller automation suite for FPS training and remote play (e.g., PlayStation 5 via Chiaki and Xbox Cloud Gaming). 

Specific targets include:
- Replicating and enhancing the capabilities of the VORTX STORE / Color Detection suite.
- Providing seamless physical controller input processing (Sony PS5 DualSense and Xbox controllers) and virtual controller actuation via ViGEmBus (`vgamepad`).
- Mirroring VORTX's 6-panel UI layout in an intuitive, high-contrast Tactical Cobalt Blue theme.
- Eliminating aiming deadzone latency and kinematic sluggishness through non-linear deflection curves, anti-deadzone punch-through, and dual-axis anti-recoil stabilization.
- Providing complete physical controller pass-through and aim-assist input blending so remote play clients (e.g. Chiaki) receive all physical inputs (sticks, triggers, buttons, D-pad) while smoothly layering aim assistance.

---

## 2. Current State
- **UI & Layout**: Re-architected in [`desktop_app.py`](file:///c:/Users/96655/ui\aim_trainer_project\desktop_app.py) into a **Left Sidebar Menu + Large Screen/Stage on the Right** (Swappable Big Screen Canvas / Settings Boards):
  - **Left Sidebar (`sidebar_left`, width ~255px)**:
    - Main action button: `⚡ تشغيل بوت التصويب [F6]`
    - Remote Play button: `🎮 ربط Chiaki / PS5`
    - Vertical navigation menu (`_tab_buttons`):
      1. `📺 شاشة المعاينة الكبيرة` (Default Big Screen)
      2. `🎯 التصويب والفيزياء` (Aim & Kinematics Board)
      3. `🎮 يد التحكم والإدخال` (Controller & Input Board)
      4. `💥 مانع الارتداد المزدوج` (Dual Anti-Recoil Board)
      5. `🎨 الرؤية والذكاء الاصطناعي` (Vision & AI Board)
      6. `🏆 بروفايلات الألعاب والأدوات` (Game Profiles & Tools Board)
    - Quick toggles: Safe preview switch, block laptop mouse switch, Mini-HUD launcher.
  - **Central/Right Stage (`tab_container`)**:
    - **Tab 0 (Big Screen)**: Canvas expands dynamically up to 1280x720 with responsive high-resolution frame rendering in `_update_preview_feed`, target radar telemetry, window switcher, and in-game setup guide launcher.
    - **Tabs 1-5 (Settings Boards)**: Open in place of the screen with a tactical top return banner (`⬅️ العودة إلى شاشة العرض الكبيرة`) allowing one-click return to the stream.
- **Color Theme**: Tactical Cobalt Blue (`#070B14` dark navy background, `#0E1726` cards, `#2563EB` royal blue accents, and `#00D2FF` vivid cyan highlights).
- **Controller Pass-Through & Blending Engine**: Implemented `pass_through_gamepad()` on [`BotController`](file:///c:/Users/96655/ui/aim_trainer_project/bot/controller.py) and integrated into [`BotWorker`](file:///c:/Users/96655/ui/aim_trainer_project/bot/worker.py):
  - Left stick passes through directly to virtual pad.
  - Right stick blends manual aim with assist vector: $R_{\text{final}} = \text{clamp}(R_{\text{user}} + R_{\text{bot}}, -1.0, 1.0)$.
  - Triggers pass through analog depression; triggerbot overrides RT on crosshair lock.
  - Added Dual PlayStation Support (`L2_OR_L1` and `R2_OR_R1` smart triggers) so aiming activates whether the user uses default (L2) or tactical flipped (L1). Corrected DirectInput Pygame button 6/7/8/9 mapping for DualShock 4 / DualSense.
  - Added One-Click Live Controller Auto-Bind (`_listen_for_controller_bind`) and expanded all mapping dropdowns to include all 20+ PlayStation/Xbox/Mouse buttons, allowing players with any custom in-game layout to bind any physical button by simply pressing it on their controller.
  - Face buttons, bumpers, stick clicks, Options/Start, Share/Back, and D-pad are mapped and synchronized to `vgamepad` (`VDS4Gamepad` or `VX360Gamepad`).
  - When idle/bot disabled, pass-through remains active so Chiaki never loses gamepad input.
- **DirectML Neural AI Model**: Downloaded and verified unencrypted [`models/yolov8n.onnx`](file:///c:/Users/96655/ui/aim_trainer_project/models/yolov8n.onnx). Runs on DirectX 12 GPU compute via `DmlExecutionProvider` with ~26 ms latency per frame. [`LocalAIDetector`](file:///c:/Users/96655/ui/aim_trainer_project/bot/local_ai_detector.py) filters strictly for COCO class 0 (`person`) and applies `head_bias_percent` to interpolate crosshair lock directly to upper chest / head.
- **In-Game Interface Guide**: Added one-click dialog `_show_ingame_guide()` in [`desktop_app.py`](file:///c:/Users/96655/ui/aim_trainer_project/desktop_app.py) instructing users how to set Call of Duty settings (Filter 2, Enemies Magenta `#FF00FF`, Enemy Health Bars ON) and Chiaki remote play stream parameters.
- **HidHide Cloaking Integration**: Extended [`HidHideManager`](file:///c:/Users/96655/ui/aim_trainer_project/bot/gamepad.py) with elevated UAC execution helpers (`ShellExecuteW` with `runas`). Added GUI buttons in Tab 6 for one-click HidHide GUI launch, app whitelisting, and cloaking toggle.
- **Verification Status**: All 85 unit tests in `pytest` pass with 100% pass rate.

---

## 3. Active Files
- [`desktop_app.py`](file:///c:/Users/96655/ui/aim_trainer_project/desktop_app.py): CustomTkinter desktop interface, 6-tab layout builder, dynamic window resizing, HidHide cloaking hub, in-game setup guide modal, and live telemetry.
- [`config.py`](file:///c:/Users/96655/ui/aim_trainer_project/config.py): Central configuration schema, game presets (`COD_BO6_PS5`, `WARZONE_TACTICAL`, `FLICK_BEAST`), controller bindings, and JSON persistence.
- [`bot/worker.py`](file:///c:/Users/96655/ui/aim_trainer_project/bot/worker.py): Core multi-threaded capture-detect-predict-act execution loop with physical-to-virtual gamepad pass-through and aim blending.
- [`bot/controller.py`](file:///c:/Users/96655/ui/aim_trainer_project/bot/controller.py): Closed-loop kinematic math, non-linear power curve calculations, directional reversal damping, anti-deadzone punch-through, input blending, and virtual gamepad synchronization.
- [`bot/gamepad.py`](file:///c:/Users/96655/ui/aim_trainer_project/bot/gamepad.py): Physical controller polling layer supporting XInput and DirectInput/Pygame (DualSense/PS4), D-pad reading, dynamic trigger thresholding, action mapping, and elevated HidHide management.
- [`bot/vision.py`](file:///c:/Users/96655/ui/aim_trainer_project/bot/vision.py): Color space conversion, circular FOV masking, HSV tolerance thresholding, and blob detection.
- [`bot/local_ai_detector.py`](file:///c:/Users/96655/ui/aim_trainer_project/bot/local_ai_detector.py): DirectML-accelerated ONNX Runtime neural network detection engine optimized for YOLOv8/YOLO11 models.
- [`bot/capture.py`](file:///c:/Users/96655/ui/aim_trainer_project/bot/capture.py): DirectX 11 Desktop Duplication (DXGI 240Hz) and MSS screen capture backends.
- [`models/yolov8n.onnx`](file:///c:/Users/96655/ui/aim_trainer_project/models/yolov8n.onnx): Pre-trained unencrypted neural model for DirectML enemy recognition.
- [`tests/test_passthrough_and_blending.py`](file:///c:/Users/96655/ui/aim_trainer_project/tests/test_passthrough_and_blending.py): Test suite validating stick blending, axis forwarding, triggerbot actuation, and HidHide elevation helpers.

---

## 4. Changes Made
1. **Full Controller Pass-Through & Blending**:
   - Added `pass_through_gamepad()` and `_sync_vpad_buttons()` in [`bot/controller.py`](file:///c:/Users/96655/ui/aim_trainer_project/bot/controller.py) to forward physical Left Stick, Right Stick, Face Buttons, Triggers, Bumpers, Stick Clicks, and D-Pad to `vgamepad`.
   - Updated `apply_stick_deflection()` to blend manual right stick deflection with aim assist deflection ($R_{\text{final}} = R_{\text{user}} + R_{\text{bot}}$).
   - Updated [`bot/worker.py`](file:///c:/Users/96655/ui/aim_trainer_project/bot/worker.py) to run pass-through both when aiming and when idle so Chiaki never loses gamepad connection.
2. **Unencrypted YOLOv8 Model via DirectML**:
   - Downloaded and verified standard unencrypted [`models/yolov8n.onnx`](file:///c:/Users/96655/ui/aim_trainer_project/models/yolov8n.onnx).
   - Configured [`LocalAIDetector`](file:///c:/Users/96655/ui/aim_trainer_project/bot/local_ai_detector.py) to load `models/yolov8n.onnx` via `DmlExecutionProvider` (DirectX 12 GPU compute). Benchmarked at ~26 ms per frame.
   - Enhanced `postprocess()` to filter strictly for class 0 (`person`) in COCO 80-class models and apply `head_bias_percent` to target heads.
3. **In-Game Interface Setup Guide**:
   - Added `_show_ingame_guide()` dialog in [`desktop_app.py`](file:///c:/Users/96655/ui/aim_trainer_project/desktop_app.py) with visual instructions for Call of Duty (Filter 2, Enemies Magenta, Health Bars ON, Dynamic Curve) and Chiaki settings.
   - Added quick preset buttons for Magenta (`#FF00FF`) in the header bar and Tab 5.
4. **Nefarius HidHide Cloaking Hub**:
   - Added elevated management methods to `HidHideManager` (`launch_gui`, `whitelist_current_process_elevated`, `set_cloaking_elevated`).
   - Added dedicated HidHide card to Tab 6 in [`desktop_app.py`](file:///c:/Users/96655/ui/aim_trainer_project/desktop_app.py).
5. **Verification & Regression Testing**:
   - Created `tests/test_passthrough_and_blending.py`.
   - Verified 100% pass rate across all 85 pytest unit tests.
6. **Big Screen & Right Sidebar Architecture Overhaul**:
   - Re-architected [`desktop_app.py`](file:///c:/Users/96655/ui/aim_trainer_project/desktop_app.py) from horizontal tabs to a Right Sidebar Menu and a large central canvas.
   - Designed all 5 settings panels as swappable boards that replace the screen on click, featuring a top return banner `⬅️ العودة إلى شاشة العرض الكبيرة` for instant return.
   - Enhanced `_update_preview_feed` with dynamic canvas scaling up to 1280x720 high-resolution rendering at 60 FPS.
   - All 85 unit tests pass with zero regressions.

---

## 5. Verification
- `pytest` executed with 85 passed in 7.78 seconds.
- DirectML warm inference confirmed operational at ~26 ms (~40 FPS) on GPU.
- Headless GUI lifecycle verified clean.
