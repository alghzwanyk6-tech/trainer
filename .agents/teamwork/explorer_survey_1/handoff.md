# Handoff Report - Explorer 1 (Directory & Architecture Explorer)

## 1. Observation

### 1.1 Directory Path & Unicode Encoding Discovery
- **Configured Target Path**: `c:\Users\96655\Downloads\__VORTX STORE_ نسخة\VORTX STORE_ نسخة`
- **Actual Directory Layout**: Direct lookup failed because the second-level folder contains two invisible Unicode Right-to-Left Mark (RLM) characters (`\u200F\u200F`).
  - **PowerShell Hex Dump Command**:
    ```powershell
    Get-ChildItem -LiteralPath 'c:\Users\96655\Downloads\__VORTX STORE_ نسخة' | ForEach-Object { [System.BitConverter]::ToString([System.Text.Encoding]::Unicode.GetBytes($_.Name)) }
    ```
  - **Verbatim Output**: `0F-20-0F-20-56-00-4F-00-52-00-54-00-58-00-20-00-53-00-54-00-4F-00-52-00-45-00-5F-00-20-00-46-06-33-06-2E-06-29-06` (`\u200F\u200FVORTX STORE_ نسخة`)
- **Resolved Absolute Root Payload Path**:
  `C:\Users\96655\Downloads\__VORTX STORE_ نسخة\‏` + `‏VORTX STORE_ نسخة\Vortx (1)\Vortx\Vortx_buy`

### 1.2 Quantitative Inventory Statistics
- **Total Files**: 2,590 files
- **Total Directories**: 218 directories
- **Total Uncompressed Size**: 1,223.75 MB (1,283,193,737 bytes)
- **Breakdown by Major Extensions**:
  | Extension | Count | Total Size (MB) | Primary Role |
  |---|---|---|---|
  | `.png` | 811 | 17.07 MB | UI graphics, tutorials, and Qt assets |
  | *(no ext)* | 767 | 65.98 MB | Chromium / WebView2 cache blocks & metadata |
  | `.qml` | 491 | 2.20 MB | Qt 6 Quick / QML streaming UI components |
  | `.dll` | 183 | 590.84 MB | Native runtime engines & managed assemblies |
  | `.pak` | 58 | 54.04 MB | Chromium / Electron resource packages |
  | `.hyb` | 52 | 1.68 MB | Qt Quick Controls hybrid styles |
  | `.qmltypes`| 31 | 1.48 MB | QML type definitions |
  | `.node` | 18 | 25.30 MB | Node.js native FFI bindings (`koffi`) |
  | `.exe` | 7 | 359.23 MB | Native / managed / Electron application binaries |
  | `.enc` | 4 | 40.25 MB | Encrypted ONNX machine learning models |
  | `.dat` | 3 | 10.37 MB | V8/Chromium ICU data (`icudtl.dat`) |
  | `.html` | 1 | 19.42 MB | Chromium license file |
  | `.asar` | 1 | 27.78 MB | Packaged Electron application bundle |
  | `.config` | 1 | 0.002 MB | .NET Framework application config (`Vortx.exe.config`) |
  | `.ps1` | 1 | 0.010 MB | Setup GUI script (`VortxRequirements.ps1`) |
  | `.bat` | 2 | 0.005 MB | Arabic administration & launch scripts |

### 1.3 Subdirectory Structure under `Vortx_buy`
| Directory Name | Files | Subdirs | Size (MB) | Purpose / Technology |
|---|---|---|---|---|
| `dll` | 4 | 2 | 150.12 MB | Architecture-specific native OpenCV C++ bindings (`x64` & `x86`) |
| `guide` | 5 | 2 | 15.39 MB | Call of Duty MW / Warzone configuration screenshots (120Hz, enemy color, blur, FOV) |
| `models` | 4 | 0 | 40.25 MB | Encrypted ONNX YOLO detection models (`LuciferBestV2`, `LuciferStrongestV3`, etc.) |
| `rm_re_fr` | 1,497 | 62 | 275.52 MB | PlayStation 5/4 Remote Play subsystem (Qt 6.x, FFmpeg, SDL2/3, Vulkan, `lu.exe`, `Vortx Stream.exe`) |
| `runtimes` | 1 | 2 | 0.15 MB | Microsoft Edge WebView2 native loader (`win-x64\native\WebView2Loader.dll`) |
| `Very important to install` | 3 | 0 | 129.42 MB | Prerequisites: .NET 4.8 offline installer, ViGEmBus 1.22.0, HidHide 1.5.230 |
| `Vortx.exe.WebView2` | 854 | 96 | 75.84 MB | Edge WebView2 user data cache, leveldb storage, and profile from previous runs |
| `xlu` | 184 | 42 | 403.79 MB | Xbox / xCloud Remote Play subsystem (Electron 2.4.2 / Greenlight Desktop, `xlu.exe`) |

### 1.4 Binary Inventory & PE Header Architectures
Across all 208 binaries analyzed (`.exe`, `.dll`, `.node`):
- **x64 (AMD64)**: 160 binaries
- **x86 (i386)**: 32 binaries (managed .NET AnyCPU DLLs and 32-bit WiX bootstrapper installer wrappers)
- **ARM64**: 1 binary (`koffi` multi-arch unpack)

#### Executables Inventory (`.exe`)
1. **`Vortx.exe` (Main Application Entry Point)**:
   - **Disk Status**: Missing from extracted folder!
   - **Investigation of `__VORTX STORE_ نسخة.zip`**: Contains `‏‏VORTX STORE_ نسخة/Vortx (1)/Vortx/Vortx_buy/Vortx.exe` (Size: 6,599,168 bytes, SHA-256: `8f7d530905ed63c128921d080542459aa492fec43fba3c6ce4e694712ea118cb`).
   - **PE Architecture**: Machine `0x8664` (x64 AMD64), PE32+, .NET CLR Managed Assembly.
   - **Cause of Disk Absence**: Windows Defender detection log confirmed quarantine:
     ```
     ThreatName           : Trojan:Win32/Wacatac.B!ml
     InitialDetectionTime : 11/2/2026 12:27:10 AM
     Resources            : {file:_C:\Users\96655\Downloads\__VORTX STORE_ نسخة\‏‏VORTX STORE_ نسخة\Vortx (1)\Vortx\Vortx_buy\Vortx.exe}
     ```
2. **`rm_re_fr\Vortx Stream.exe`**:
   - **Size**: 7,665,152 bytes (7.31 MB), SHA-256: `d2628ae89c0ce4b452ef25e7899befe1c2cb2e236d03feee0f8df3c8cbb065ac`
   - **PE Architecture**: Machine `0x8664` (x64 AMD64), PE32+, .NET CLR Managed Assembly.
   - **Internal Metadata**: `OriginalFilename: Color Detection.exe`, `ProductName: Vortx`, `FileVersion: 2.5.0.0`.
   - **Technology**: Windows Forms host with embedded Edge WebView2 UI, OpenCvSharp, FlashCap, and DirectML.
3. **`rm_re_fr\lu.exe`**:
   - **Size**: 6,139,904 bytes (5.86 MB)
   - **PE Architecture**: Machine `0x8664` (x64 AMD64), PE32+, Native C++ (MSYS2/MinGW-w64).
   - **Internal Metadata**: `OriginalFilename: lu.exe`, `FileDescription: VORTX PS5 Remote`, `FileVersion: 1.10.0.0`.
   - **Origin**: Rebranded and customized fork of Chiaki / Chiaki-ng (open-source PlayStation Remote Play client).
4. **`xlu\xlu.exe`**:
   - **Size**: 227,062,784 bytes (216.54 MB)
   - **PE Architecture**: Machine `0x8664` (x64 AMD64), PE32+, Native Electron runtime.
   - **Origin**: Extracted `xlu\resources\app.asar/package.json` confirms:
     ```json
     {
       "name": "greenlight-desktop",
       "productName": "Lucifer",
       "description": "Lucifer is a streaming application for Xbox and xCloud",
       "version": "2.4.2",
       "main": "app/background.js"
     }
     ```
5. **`Very important to install\NDP48-x86-x64-AllOS-ENU.exe`**:
   - **Size**: 121,346,568 bytes (115.73 MB). Official Microsoft .NET Framework 4.8 offline installer.
6. **`Very important to install\ViGEmBus_1.22.0_x64_x86_arm64.exe`**:
   - **Size**: 6,278,576 bytes (5.99 MB). Nefarius Virtual Gamepad Emulation Bus installer.
7. **`Very important to install\HidHide_1.5.230_x64.exe`**:
   - **Size**: 8,078,016 bytes (7.70 MB). Nefarius HidHide device hiding filter driver installer.
8. **`xlu\resources\elevate.exe`**:
   - **Size**: 107,520 bytes (0.1 MB). Helper utility to trigger UAC elevation.

### 1.5 Scripts and Configuration Files
- **`Vortx.exe.config`**:
  - Targets `.NETFramework,Version=v4.7.2`.
  - Configures runtime assembly binding redirects for `System.Buffers` (4.0.5.0), `System.Memory` (4.0.5.0), `System.Numerics.Vectors` (4.1.6.0), `System.Runtime.CompilerServices.Unsafe` (6.0.3.0), `System.Resources.Extensions` (10.0.0.13), and `System.Drawing.Common` (10.0.0.0).
- **`VortxRequirements.ps1`**:
  - WinForms PowerShell GUI written in Arabic titled `"Vortx | إعداد المتطلبات"`.
  - Checks 4 prerequisites via registry / service checks:
    1. `.NET Framework 4.7.2 أو أحدث` (Release >= 461808)
    2. `Microsoft Edge WebView2`
    3. `ViGEmBus` driver service
    4. `HidHide` driver service
  - Automatically invokes silent installations from `Very important to install\` and downloads WebView2 Evergreen bootstrapper from Microsoft if missing.
  - Launches `Vortx.exe` upon completion.
- **`المـــتــطلبات.bat`**:
  - Launcher that starts PowerShell bypassing execution policy:
    `powershell.exe -NoProfile -ExecutionPolicy Bypass -STA -File "%~dp0VortxRequirements.ps1"`
- **`التعــــــريفات.bat`**:
  - Administrative maintenance script titled `"Vortx - Allow Helper"`.
  - Self-elevates to Administrator via UAC.
  - Adds Windows Defender folder exclusion (`Add-MpPreference -ExclusionPath`) and process exclusions for `Vortx.exe`, `rm_re_fr\lu.exe`, and `xlu\Lucifer.exe`.
  - Configures inbound and outbound Windows Defender Firewall rules (`netsh advfirewall firewall add rule`).
  - Flushes DNS cache (`ipconfig /flushdns`).
  - Resets stuck WinHTTP proxy (`netsh winhttp reset proxy` and `ProxyEnable = 0`).
  - Forces system time resynchronization using NTP pool (`w32tm /resync /force`) to ensure licensing token timestamps match authentication servers.

### 1.6 Machine Learning Assets
Located in `Vortx_buy\models\`:
- `Lucifer-Head-only.onnx.enc` (10,604,564 bytes ~10.60 MB)
- `LuciferBestV2-5.onnx.enc` (10,569,988 bytes ~10.57 MB)
- `LuciferBestV2.onnx.enc` (10,569,988 bytes ~10.57 MB)
- `LuciferStrongestV3.onnx.enc` (10,457,380 bytes ~10.46 MB)
All models are encrypted ONNX format (`.onnx.enc`) corresponding to YOLO nano/small object detection models trained for player body and head detection. Decryption and inference are managed through `Microsoft.ML.OnnxRuntime.dll` and `DirectML.dll`.

---

## 2. Logic Chain

1. **Path Resolution**: Examination of the directory `c:\Users\96655\Downloads\__VORTX STORE_ نسخة` revealed that the subdirectory name contained two leading Unicode 0x200F (RLM) characters. Decoding and traversing this path confirmed that the entire functional package is encapsulated under `Vortx_buy`.
2. **Missing Executable Root Cause**: The configuration file `Vortx.exe.config`, cache folder `Vortx.exe.WebView2`, and script references in `VortxRequirements.ps1` all expect `Vortx.exe` in `Vortx_buy`. Querying Windows Defender (`Get-MpThreatDetection`) proved that `Vortx.exe` was quarantined on `11/2/2026 12:27:10 AM` as `Trojan:Win32/Wacatac.B!ml`. Inspecting `__VORTX STORE_ نسخة.zip` confirmed that `Vortx.exe` (6.6 MB x64 .NET assembly) is present in the archive.
3. **Architecture Mapping**:
   - Analysis of PE headers of the 208 binaries confirmed that the engine is exclusively 64-bit Windows (`x64 AMD64`), utilizing DirectML for DirectX 12 hardware acceleration across AMD, NVIDIA, and Intel GPUs.
   - The application is a composite system composed of three distinct subsystems:
     1. **Streaming & Ingestion**:
        - PlayStation Remote Play: Handled by `rm_re_fr\lu.exe` (a Chiaki fork) using shared memory (`ChiakiFrameShare`, zero-copy raw BGRA).
        - Xbox / Cloud Gaming: Handled by `xlu\xlu.exe` (Greenlight Desktop Electron app) exposing an MJPEG / shared-memory stream on `http://127.0.0.1:9003`.
        - PC / Capture Card: Handled via `FlashCap.dll` (DirectShow capture from Elgato/AverMedia) or direct Desktop DC screen grabbing.
     2. **Detection & AI Core**:
        - High-speed frame processing using OpenCV (`OpenCvSharp.dll` + `OpenCvSharpExtern.dll`).
        - Dual targeting engine: Color-based marker tracking (in-game enemy colors: green/magenta/purple) and AI neural network object detection using ONNX Runtime DirectML models.
     3. **Control Output & Stealth**:
        - Controller emulation using ViGEmBus (`Nefarius.ViGEm.Client.dll`) creating a virtual Xbox 360 / DualShock 4 controller.
        - Stealth isolation using HidHide (`\\.\HidHide`) to block physical controller inputs from conflicting with emulated inputs.
4. **Environment & Dependency Chain**:
   - No Python installation is needed (the 3 `.py` files found are non-functional build artifacts inside `koffi`).
   - No Node.js runtime installation is needed (Electron packages its own runtime).
   - The mandatory prerequisites are strictly: Windows 10/11 x64, .NET Framework 4.7.2 or 4.8, Microsoft Edge WebView2 Evergreen, ViGEmBus driver, and HidHide driver.

---

## 3. Caveats

1. **Quarantined Main Binary**: Because `Vortx.exe` was quarantined by Windows Defender during initial archive extraction, its PE header and IL metadata were analyzed directly from the uncorrupted `.zip` archive entry in memory.
2. **Encrypted ONNX Models**: The four model files in `models\` have a proprietary `.enc` wrapper. The runtime decryption key is embedded or negotiated dynamically via the licensing server during token authentication.
3. **Licensing Server Access**: Full live runtime execution requires a valid license token and active connection to the licensing endpoint (`Enter Access Token` / `token, hwid, nonce`).

---

## 4. Conclusion

The inspected project `VORTX STORE` is a sophisticated, turnkey, hardware-accelerated computer vision and AI aim-assist application for console and PC gaming. It is engineered with:
- A .NET 4.7.2 x64 host application with an Edge WebView2 user interface.
- DirectML and ONNX Runtime for GPU-accelerated object detection.
- Customized forks of open-source streaming clients: Chiaki (`lu.exe` for PS5) and Greenlight Desktop (`xlu.exe` for Xbox).
- Low-latency virtual controller injection via ViGEmBus and HidHide kernel drivers.
- Automated prerequisite provisioning via `VortxRequirements.ps1` and system security configuration scripts (`التعــــــريفات.bat`).

---

## 5. Verification Method

To independently verify these findings, run the following commands in PowerShell from the project root:

1. **Verify Unicode Path and Core Directory Structure**:
   ```powershell
   $root = 'c:\Users\96655\Downloads\__VORTX STORE_ نسخة'
   $vortx_buy = (Get-ChildItem -LiteralPath $root -Recurse | Where-Object { $_.Name -eq 'Vortx_buy' -and $_.Attributes -match 'Directory' }).FullName
   Get-ChildItem -LiteralPath $vortx_buy -Directory | Select-Object Name
   ```
2. **Verify PE Machine Architectures and CLR Assemblies**:
   ```powershell
   python c:\Users\96655\ui\aim_trainer_project\.agents\teamwork\explorer_survey_1\inspect_pe.py
   ```
3. **Verify Defender Quarantine Event**:
   ```powershell
   Get-MpThreatDetection | Where-Object { $_.Resources -match 'Vortx.exe' } | Format-List ThreatName, InitialDetectionTime, Resources
   ```
4. **Verify Vortx.exe Inside the Original Archive**:
   ```powershell
   Add-Type -AssemblyName System.IO.Compression.FileSystem
   [System.IO.Compression.ZipFile]::OpenRead('c:\Users\96655\Downloads\__VORTX STORE_ نسخة.zip').Entries | Where-Object { $_.FullName -match 'Vortx\.exe$' } | Select-Object FullName, Length
   ```
5. **Verify Greenlight Package Metadata from `app.asar`**:
   ```powershell
   python c:\Users\96655\ui\aim_trainer_project\.agents\teamwork\explorer_survey_1\inspect_asar.py
   ```
