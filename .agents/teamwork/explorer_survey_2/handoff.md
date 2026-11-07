# Technical Survey & Component Architecture Report: VORTX STORE / Lucifer

**Explorer**: Explorer 2 (Component & Technology Explorer)  
**Date**: 2026-11-06  
**Target Root**: `c:\Users\96655\Downloads\__VORTX STORE_ نسخة\‏‏VORTX STORE_ نسخة\Vortx (1)\Vortx\Vortx_buy`  
**Reference Companion**: `c:\Users\96655\Downloads\Color_detection\Color Detection_Secure`  

---

## 1. Observation

### 1.1 Root Location & Directory Path Resolution
Direct access to `c:\Users\96655\Downloads\__VORTX STORE_ نسخة\VORTX STORE_ نسخة` failed initially because the inner subdirectory name contains two Unicode Right-to-Left (RLM) mark bytes (`\u200f\u200f`). The resolved absolute directory path containing the active payload is:
```text
c:\Users\96655\Downloads\__VORTX STORE_ نسخة\‏‏VORTX STORE_ نسخة\Vortx (1)\Vortx\Vortx_buy\
```
A non-quarantined release copy with intact debugging symbols was discovered at:
```text
c:\Users\96655\Downloads\Color_detection\Color Detection_Secure\
```

### 1.2 Binary Inventory & Status

| Binary / Executable | Relative Path | Size | Type / Architecture | Observed Status |
|---|---|---|---|---|
| `Vortx.exe` | Root of `Vortx_buy` | ~2.2 MB | .NET Framework 4.7.2 + WebView2 WinForms | Quarantined by Windows Defender as `Trojan:Win32/Wacatac.B!ml` |
| `Vortx Stream.exe` | `rm_re_fr/Vortx Stream.exe` | 7,665,152 bytes | C# .NET WPF/WinForms (Assembly: `Color Detection, v2.5.0.0`) | Active; contains AI vision engine (`lucifer_cv2`) |
| `lu.exe` | `rm_re_fr/lu.exe` | 6,139,904 bytes | C++20 / Qt6 / SDL3 / FFmpeg / libplacebo | Active; custom fork of Chiaki (PlayStation Remote Play) |
| `xlu.exe` | `xlu/xlu.exe` | 227,062,784 bytes | Packaged Electron v30+ binary | Active; custom fork of Greenlight (Xbox Cloud/Remote Play) |
| `HidHide_1.5.230_x64.exe` | `Very important to install/` | 8,078,016 bytes | Windows Kernel Driver Installer | Driver for masking physical gamepads from OS |
| `ViGEmBus_1.22.0_x64...exe` | `Very important to install/` | 6,278,576 bytes | Windows Kernel Driver Installer | Driver for emulating virtual Xbox 360 gamepads |
| `NDP48-x86-x64-AllOS-ENU.exe` | `Very important to install/` | 121,346,568 bytes | Microsoft Runtime Installer | .NET Framework 4.8 runtime installer |

### 1.3 Windows Defender Threat Detection Log
PowerShell `Get-MpThreatDetection` confirmed verbatim:
```text
ThreatName           : Trojan:Win32/Wacatac.B!ml
SeverityID           : 5 (Severe)
ActionSuccess        : True
Resources            : file:_C:\Users\96655\Downloads\__VORTX STORE_ نسخة\‏‏VORTX STORE_ نسخة\Vortx (1)\Vortx\Vortx_buy\Vortx.exe
```

### 1.4 Entry Point Batch Scripts & Prerequisites
- **`التعــــــريفات.bat`**: Elevates to Administrator, executes:
  - `Add-MpPreference -ExclusionPath '%APPDIR%'` and `Add-MpPreference -ExclusionProcess '%APPEXE%'`
  - Adds inbound/outbound Windows Firewall rules for `%APPEXE%`, `rm_re_fr\lu.exe`, `xlu\Lucifer.exe`
  - Runs `ipconfig /flushdns` and clears WinHTTP proxy (`netsh winhttp reset proxy`, `ProxyEnable = 0`)
  - Configures and resyncs NTP time against `time.windows.com,0x9 pool.ntp.org,0x9`
- **`المـــتــطلبات.bat`**: Launches `VortxRequirements.ps1` with `-ExecutionPolicy Bypass -STA`.
- **`VortxRequirements.ps1`**: A WinForms utility checking:
  1. `.NET Framework 4.7.2+` (Registry `Release >= 461808`)
  2. `Microsoft Edge WebView2` (Registry `{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}`)
  3. `ViGEmBus` driver service
  4. `HidHide` driver service
  Launches `Vortx.exe` once verified.

### 1.5 Electron Application (`xlu`) Disassembly & Deobfuscation
- **`xlu/resources/app.asar`**: 29,124,517 bytes containing 4,922 files.
- **`package.json`** inside `app.asar`:
  ```json
  {
    "private": true,
    "name": "greenlight-desktop",
    "productName": "Lucifer",
    "description": "Lucifer is a streaming application for Xbox and xCloud",
    "version": "2.4.2",
    "author": "Lucifer",
    "main": "app/background.js",
    "dependencies": {
      "axios": "^1.16.0",
      "electron-serve": "^3.0.0",
      "electron-store": "^8.1.0",
      "express": "^5.2.1",
      "koffi": "^2.9.0",
      "xal-node": "^1.1.6-beta2",
      "xbox-webapi": "^2.0.0-beta4",
      "xbox-xcloud-player": "^0.2.11"
    }
  }
  ```
- **`app/background.js`**: JavaScript Obfuscator encoded. Evaluation of deobfuscator table yielded 971 string tokens, including:
  - Arabic authentication template: `"تسجيل الدخول إلى Lucifer"`, `"افتح الرابط التالي في المتصفح وأدخل الرمز لتسجيل الدخول بحساب Xbox / Microsoft:"`, `"https://microsoft.com/link"`
  - Express stream endpoints: `"/api/stream/frame.jpg"`, `"/api/:channel/:action"`, `"/api/stream/status"`
  - FFI loading of `koffi` and `xinput9_1_0.dll`

### 1.6 C# .NET AI Core (`Vortx Stream.exe` / `Color Detection.exe`) PDB Symbol Analysis
Inspection of `Color Detection.pdb` (572,928 bytes) revealed 84 source files in project `lucifer_cv2`:
```text
lucifer_cv2\Program.cs
lucifer_cv2\AppConfig.cs
lucifer_cv2\EnvironmentGuard.cs
lucifer_cv2\Form1.cs / Form1.Designer.cs
lucifer_cv2\LicenseManager.cs
lucifer_cv2\LoginScreen.cs / LoginScreen.Designer.cs
lucifer_cv2\Capture\CaptureManager.cs
lucifer_cv2\Capture\DXGICapture.cs
lucifer_cv2\Capture\GPUInfo.cs
lucifer_cv2\Capture\HighFPSCaptureControl.cs
lucifer_cv2\Capture\ICaptureMethod.cs
lucifer_cv2\Stream\LuciferAPI.cs
lucifer_cv2\Stream\RegistrationControl.cs
lucifer_cv2\Stream\SettingsControl.cs
lucifer_cv2\Stream\SetupWizard.cs
lucifer_cv2\UI\AimPanelControl.cs
lucifer_cv2\UI\ColorPanelControl.cs
lucifer_cv2\UI\ControllerPanelControl.cs
lucifer_cv2\UI\GamePanelControl.cs
lucifer_cv2\UI\HowToPanelControl.cs
lucifer_cv2\UI\PreviewPanelControl.cs
lucifer_cv2\UI\RecoilPanelControl.cs
```

### 1.7 Network & Authentication Endpoints Extracted
From binary string tables:
- **Licensing & Authentication Backend**:
  - `https://urscript.shop:3000`
  - `https://luciferstore.store:3000/customer`
  - `https://lucifer-scriptss.com/`
  - Endpoints: `/api/c/activate`, `/api/c/heartbeat`, `/api/c/verify`
  - Token Format: JWT string beginning with `URS-...`, bound to device HWID (`hwid claim`)
- **Console Registration & Account Resolution**:
  - `https://www.psntools.com/psn/checker`
  - `https://psn.flipscreen.games/search.php?`
  - `https://microsoft.com/link`
- **Internal Inter-Process Communication (IPC)**:
  - `http://127.0.0.1:9003` (`/api/stream/mjpeg` - exposed by `lu.exe`)
  - `http://127.0.0.1:5218` (exposed by `xlu.exe` for Xbox frame capture)

---

## 2. Logic Chain

1. **Launcher & Missing Binary Identification**:
   - *Observation*: `Vortx.exe.config` and directory `Vortx.exe.WebView2` existed in `Vortx_buy`, but `Vortx.exe` was absent.
   - *Observation*: PowerShell `Get-MpThreatDetection` recorded `Vortx.exe` quarantined on 11/2/2026 as `Trojan:Win32/Wacatac.B!ml`.
   - *Inference*: `Vortx.exe` was deleted/isolated by Windows Defender upon initial extraction. The author included `التعــــــريفات.bat` specifically to add Defender exclusions and prevent this quarantine. A clean unquarantined copy survives in `Downloads\Color_detection\Color Detection_Secure\Color Detection.exe`.

2. **System Architecture & Multi-Process Decoupling**:
   - *Observation*: The application comprises three distinct runtime engines: `Vortx Stream.exe` (.NET C#), `lu.exe` (Qt6 C++), and `xlu.exe` (Electron).
   - *Observation*: `Vortx Stream.exe` contains explicit HTTP client classes (`lucifer_cv2.Stream.LuciferAPI` and `XboxLuciferAPI`) making requests to `http://127.0.0.1:9003` and `http://127.0.0.1:5218`.
   - *Inference*: The project does not render console game streams in a single monolith. Instead, it offloads video streaming and console handshakes to customized open-source clients (`lu.exe` for PlayStation via Chiaki, and `xlu.exe` for Xbox via Greenlight), which run local webservers streaming video frames over localhost to `Vortx Stream.exe`.

3. **Computer Vision & Hardware-Accelerated AI Pipeline**:
   - *Observation*: `Vortx_buy` bundles `Microsoft.ML.OnnxRuntime.dll`, `DirectML.dll`, `OpenCvSharp.dll`, `OpenCvSharpExtern.dll`, and four `.onnx.enc` files (`Lucifer-Head-only.onnx.enc`, `LuciferBestV2-5.onnx.enc`, `LuciferBestV2.onnx.enc`, `LuciferStrongestV3.onnx.enc`).
   - *Observation*: Source files include `DXGICapture.cs`, `HighFPSCaptureControl.cs`, `AimPanelControl.cs`, and `RecoilPanelControl.cs`.
   - *Inference*: Video frames captured from DXGI screen duplication, Elgato capture card, or localhost MJPEG stream are preprocessed using OpenCV, passed to ONNX Runtime via DirectML on GPU for object detection (enemy bodies/heads in Call of Duty BO6/BO7), and post-processed for aim bias, smoothing, and recoil compensation.

4. **Input Injection & Gamepad Masking**:
   - *Observation*: Bundles `Nefarius.ViGEm.Client.dll`, installer `ViGEmBus_1.22.0...exe`, and installer `HidHide_1.5.230...exe`.
   - *Observation*: String references `Games will ONLY see Xbox 360 Controller (ViGEm)`, `HidHideCLI.exe`, `Physical controller hidden from games!`.
   - *Inference*: To bypass input detection and achieve seamless controller aim assistance, `HidHide` hides the user's physical controller from the game process, while `Vortx Stream.exe` intercepts physical controller input, injects algorithmic aim corrections, and outputs synthetic controller state through a virtual Xbox 360 gamepad managed by `ViGEmBus`.

---

## 3. Architecture Diagrams & Call Graphs

### 3.1 High-Level Component Interaction Diagram

```mermaid
flowchart TD
    subgraph UI_Launcher ["Launcher & Store Layer"]
        VortxExe["Vortx.exe / Color Detection.exe<br/>(.NET 4.7.2 + WebView2)"]
        Batch1["التعــــــريفات.bat<br/>(Defender & Firewall Config)"]
        Batch2["VortxRequirements.ps1<br/>(Prerequisite Validator)"]
    end

    subgraph Streaming_Layer ["Console Streaming Subsystems"]
        LU["rm_re_fr/lu.exe<br/>(Qt6 / SDL3 Chiaki Fork)<br/>Listens: 127.0.0.1:9003"]
        XLU["xlu/xlu.exe<br/>(Electron / Next.js Greenlight Fork)<br/>Listens: 127.0.0.1:5218"]
    end

    subgraph AI_Core ["Core AI & Vision Engine (Vortx Stream.exe)"]
        CapMgr["CaptureManager.cs<br/>(DXGI / FlashCap / MJPEG)"]
        OpenCV["OpenCvSharp + OpenCvSharpExtern<br/>(Frame Preprocessing & FOV Crop)"]
        OnnxML["OnnxRuntime + DirectML.dll<br/>(GPU Inference on .onnx.enc Models)"]
        AimCtrl["AimPanelControl + RecoilPanelControl<br/>(Aim Smoothing & Anti-Recoil Math)"]
        LicMgr["LicenseManager.cs<br/>(JWT Token & HWID Heartbeat)"]
    end

    subgraph Gamepad_Layer ["Virtual Gamepad & Masking"]
        ViGEm["Nefarius.ViGEm.Client.dll<br/>(Virtual Xbox 360 Controller)"]
        HidHide["HidHide Kernel Driver<br/>(Mask Physical Gamepad)"]
    end

    subgraph External_Cloud ["External Services & Auth"]
        LicServer["https://urscript.shop:3000<br/>https://luciferstore.store:3000<br/>(/api/c/activate, /api/c/heartbeat)"]
        PSN["psntools.com / flipscreen.games<br/>(PSN Account ID Lookup)"]
        MSFT["microsoft.com/link<br/>(Xbox OAuth Device Flow)"]
    end

    Batch1 -.-> VortxExe
    Batch2 -.-> VortxExe
    VortxExe -->|Launches / Orchestrates| AI_Core
    VortxExe -->|Loads Webview| PSN

    LU -->|MJPEG Frame Stream (Port 9003)| CapMgr
    XLU -->|Frame Stream (Port 5218)| CapMgr
    XLU <-->|OAuth Code| MSFT

    CapMgr --> OpenCV --> OnnxML --> AimCtrl
    AimCtrl --> ViGEm -->|Synthetic Gamepad Input| GameOS[Target Game Engine]
    HidHide -.->|Blocks Direct Input| GameOS

    LicMgr <-->|Token & Heartbeat| LicServer
```

### 3.2 Detection & Input Event Pipeline

```text
[Video Source: PS Remote Play (lu.exe) OR Xbox Stream (xlu.exe) OR Desktop DXGI]
                          │
                          ▼ (HTTP / MJPEG / Desktop Duplication)
             CaptureManager.cs (DXGICapture / FlashCap)
                          │
                          ▼ (Raw BGR / BGRA Frame Buffer)
                 OpenCvSharp Preprocessing
           - Color format conversion (BGR -> RGB)
           - Detection zone / FOV bounding box crop
           - Normalization
                          │
                          ▼ (Tensor float32[1, 3, H, W])
           Microsoft.ML.OnnxRuntime + DirectML.dll
           Inference on Decrypted Model:
           [LuciferBestV2-5.onnx / Lucifer-Head-only.onnx]
                          │
                          ▼ (Bounding Boxes, Confidence Scores, Class Labels)
                Aim Assist & Tracking Logic
           - Filter by minTargetConfidence & FOV limit
           - Continuous tracking interpolation between frames
           - Aim Bias From Top (Head priority offset)
           - Smoothing factor interpolation
           - Anti-recoil weapon offset compensation
                          │
                          ▼ (Adjusted Thumbstick X/Y Coordinates)
                   ViGEm Gamepad Output
           - Physical gamepad masked via HidHide driver
           - Virtual Xbox 360 controller reports injected to Windows OS
```

---

## 4. Caveats

1. **`Vortx.exe` Execution Quarantine**: Executing `Vortx.exe` directly from the primary download folder without applying Defender exclusion rules will fail because Windows Defender immediately removes the file. Running `Color Detection.exe` from `Downloads\Color_detection\Color Detection_Secure\` or running `التعــــــريفات.bat` as Administrator is required to unblock execution.
2. **Encrypted ONNX Assets**: Models in `models/*.onnx.enc` are encrypted at rest using an AES key verified inside `EnvironmentGuard.cs` / `LicenseManager.cs`. Direct inspection of raw model layers requires extracting the in-memory decrypted stream during initialization.
3. **Live Licensing Server Dependency**: The application will not operate past the login screen without a valid active token starting with `URS-...` signed by `https://urscript.shop:3000`. Offline operation requires spoofing `/api/c/activate` and `/api/c/heartbeat` or patching `LicenseManager.VerifyAsync`.

---

## 5. Conclusion

VORTX STORE / Lucifer is an enterprise-grade, distributed AI aim-assist and streaming automation system for Call of Duty (Black Ops 6, Black Ops 7, and Modern Warfare). The technical architecture is summarized as follows:

1. **User Interface & Presentation**:
   - **Store/Launcher**: WinForms embedding Microsoft Edge WebView2, integrating Discord and PSNTools.
   - **AI Controller UI**: Dark-themed WPF/WinForms interface (`lucifer_cv2.UI`) featuring modular controls for FOV, aim smoothing, confidence thresholds, and anti-recoil curves.
   - **Streaming GUIs**: Qt6/QML for PlayStation streaming (`lu.exe`) and Electron + Next.js with Arabic RTL support for Xbox streaming (`xlu.exe`).
2. **Vision & Inference Engine**:
   - Hardware-accelerated GPU pipeline leveraging `Microsoft.ML.OnnxRuntime` with `DirectML` and `OpenCvSharp`.
   - Supports local desktop capture (DXGI), capture card input (FlashCap), and remote network capture over localhost HTTP ports (`9003` and `5218`).
3. **Input & Evasion Architecture**:
   - Virtual gamepad emulation through `ViGEmBus` combined with kernel-level gamepad hiding via `HidHide`, allowing external aim assist without injecting into game process memory.
4. **Cloud & Licensing**:
   - Remote authorization with JWT token verification (`URS-...`), HWID machine locking, periodic HTTP heartbeat polling, and Microsoft OAuth device authentication.

---

## 6. Verification Method

To independently verify these findings on the local machine:

1. **Verify Windows Defender Quarantine**:
   ```powershell
   Get-MpThreatDetection | Select-Object -First 3 ThreatName, InitialDetectionTime, Resources
   ```
2. **Verify Electron Package Metadata**:
   ```powershell
   node -e "const fs = require('fs'); const asar = 'c:\\Users\\96655\\Downloads\\__VORTX STORE_ نسخة\\‏‏VORTX STORE_ نسخة\\Vortx (1)\\Vortx\\Vortx_buy\\xlu\\resources\\app.asar'; const fd = fs.openSync(asar, 'r'); const b = Buffer.alloc(16); fs.readSync(fd, b, 0, 16, 0); const s = (16 + b.readUInt32LE(12) + 3) & ~3; const buf = Buffer.alloc(1103); fs.readSync(fd, buf, 0, 1103, s); console.log(buf.toString('utf8'));"
   ```
3. **Verify .NET Assembly Identity**:
   ```powershell
   $path = (Get-ChildItem 'c:\Users\96655\Downloads' -Filter 'Vortx Stream.exe' -Recurse | Select-Object -First 1).FullName
   [System.Reflection.AssemblyName]::GetAssemblyName($path)
   ```
4. **Verify Extracted PDB Source Files**:
   Inspect `c:\Users\96655\ui\aim_trainer_project\.agents\teamwork\explorer_survey_2\inspect_pdb.py` or view `c:\Users\96655\Downloads\Color_detection\Color Detection_Secure\Color Detection.pdb`.
