# Machine Learning & Advanced Assets Technical Report (Explorer 3 Survey)

**Target Project**: `c:\Users\96655\Downloads\__VORTX STORE_ نسخة\VORTX STORE_ نسخة` (and associated zip `__VORTX STORE_ نسخة.zip`)  
**Investigator**: Explorer 3 (Machine Learning & Advanced Assets Explorer)  
**Date**: 2026-11-06  
**Status**: COMPLETE (Hard Handoff)

---

## 1. Observation

### 1.1 Directory Structure & File Locations
The primary application bundle is located at:
`c:\Users\96655\Downloads\__VORTX STORE_ نسخة\‏‏VORTX STORE_ نسخة\Vortx (1)\Vortx\Vortx_buy\`
(Note: The directory name contains Unicode Right-to-Left marks `\u200F\u200F` before `VORTX STORE_ نسخة`, hex bytes `E2-80-8F-E2-80-8F-56-4F-52-54-58-20-53-54-4F-52-45-5F-20-D9-86-D8-B3-D8-AE-D8-A9`).

The core binary `Vortx.exe` (size: 6,599,168 bytes, CLR assembly `Vortx, Version=2.5.0.0`) is present in the archive `__VORTX STORE_ نسخة.zip` and executed from the `Vortx_buy` directory.

### 1.2 Machine Learning Models Inventory
Four proprietary encrypted neural network models reside in `Vortx_buy\models\`:
1. `Lucifer-Head-only.onnx.enc`
   - Size: `10,604,564 bytes` (~10.11 MB)
   - Magic Header: First 4 bytes are ASCII `LCM1` (`0x4C 0x43 0x4D 0x31` = "Lucifer Crypto Model 1")
   - UI Display Name: `"AIO HEADS (head-only - turn OFF shape filter)"`
   - Target Classes: Head only (`IsHead = true`)
   - Default Input Resolution: `640x640`
2. `LuciferBestV2-5.onnx.enc`
   - Size: `10,569,988 bytes` (~10.08 MB)
   - Magic Header: `LCM1`
   - UI Display Name: `"VORTX V2.5 / VORTX V2 (yolo11m, body/head)"`
   - Target Classes: `body` (Class 0: player bodies), `head` (Class 1)
   - Default Input Resolution: `640x640`
3. `LuciferBestV2.onnx.enc`
   - Size: `10,569,988 bytes` (~10.08 MB)
   - Magic Header: `LCM1`
   - UI Display Name: `"VORTX V2 (yolo11m, body/head)"`
   - Target Classes: `body`, `head`
   - Default Input Resolution: `640x640`
4. `LuciferStrongestV3.onnx.enc`
   - Size: `10,457,380 bytes` (~9.97 MB)
   - Magic Header: `LCM1`
   - UI Display Name: `"VORTX V3 (yolo11m BO7, body/head/teammate)"`
   - Target Classes: `body`, `head`, `teammate` (Class 2: friendly players to ignore)
   - Default Input Resolution: `640x640` (with `VORTX_V3_HD` supporting `1280x1280`)

Additionally, an embedded base64 ONNX verification model (`verifier.onnx` / `statue.onnx`) is embedded in string `#US` token `0x1d71` starting with `CAcSB3B5dG9yY2gaBjIuMTEuMDqF7RYKtAEKAXgKDW9ubng6OkNvbnZfNTk...`:
- Producer: PyTorch 2.11.0 export
- Architecture: Convolutional feature extractor (`/f/f.0/f.0.0/Conv` through `/f/f.8/MaxPool`), Flatten (`/head/head.0/Flatten`), followed by Gemm dense classification layers (`/head/head.2/Gemm`, `/head/head.4/Gemm`).

### 1.3 Model Presets Recognized in Binary Metadata
The user string table (`#US`) defines friendly presets and model specifications:
| Model Name | Internal Identifier | Architecture | Resolution | Target Classes / Description |
|---|---|---|---|---|
| `VORTX V3 HD` | `VORTX_V3_HD.onnx` | YOLO11m (BO7) | 1280x1280 | Max range, high-resolution BO7 detection |
| `VORTX V3` | `VORTX_V3.onnx` | YOLO11m (BO7) | 640x640 | `body`, `head`, `teammate` |
| `VORTX V2` | `VORTX_V2.onnx` | YOLO11m | 640x640 | `body`, `head` |
| `SUNXDS 0.8` | `sunxds` | YOLOv8s | 640x640 | `player`, `head` |
| `AIO HEADS` | `AIOHeads` | YOLOv8/11 custom | 640x640 | Head-only |
| `WARZONE 50k v2` | `WZ_50k_v2` / `_320` | YOLOv8n | 320x320 | Low-latency enemy detection |
| `WARZONE 50k` | `WZ_` | YOLOv8s | 640x640 | Enemy class |
| `BO6 PURPLE` | `BO6_PURPLE` | YOLOv8s | 640x640 | Enemy marker detection |
| `BO7 NAMETAGS` | `NameTags` | YOLOv8s | 640x640 | Enemy nametag marker |
| `ENFORCER v2` | `Enforcer` | YOLOv8s | 640x640 | Enemy body detection |
| `RIVALS v4` | `Rivals` | YOLOv8s | 640x640 | Enemy detection |

### 1.4 Inference Engines & Runtime Dependencies
1. **Primary Inference Engine**: Microsoft ONNX Runtime (`Microsoft.ML.OnnxRuntime.dll` [v1.x], native `onnxruntime.dll` 13,804,000 bytes).
2. **Hardware Acceleration Engine**: DirectML Execution Provider (`DirectML.dll` 27,383,832 bytes, `DirectML.Debug.dll` 2,197,944 bytes).
   - Direct MemberRef: `Microsoft.ML.OnnxRuntime.SessionOptions::AppendExecutionProvider_DML(int deviceId)`
   - Hardware target: DirectX 12 D3D11/D3D12 GPU compute (vendor agnostic: NVIDIA GeForce, AMD Radeon, Intel Arc/Iris, Qualcomm).
   - CPU Fallback: Standard ONNX Runtime CPU execution provider if DirectML fails initialization.
3. **Secondary Inference Engine**: OpenCV DNN (`OpenCvSharp.Dnn.CvDnn::ReadNetFromOnnx`, `OpenCvSharp.Dnn.Net::SetInput`, `Net::Forward`).
4. **Computer Vision Runtime**: OpenCvSharp v4.11.0 (`OpenCvSharp.dll` 959 KB, `OpenCvSharpExtern.dll` 62,044,672 bytes, `opencv_videoio_ffmpeg4110_64.dll` 27,954,688 bytes).
5. **Gamepad Virtualization**: ViGEm Client (`Nefarius.ViGEm.Client.dll` 290,304 bytes) communicating with system driver `ViGEmBus.sys`.
6. **Device Cloaking**: `HidHideApi` communicating with `HidHide.sys` to cloak physical game controllers.

### 1.5 Detailed Code Structures in `Vortx.exe`

#### A. Model Decryption & Loading (`lucifer_cv2.YoloDetector..ctor`)
- Encrypted file check: `modelPath.EndsWith(".enc")`
- File header check: Validates 4-byte signature `LCM1` (`0x4C434D31`).
- In-memory decryption: Decrypts encrypted payload using AES-CBC/AES-GCM into a memory buffer (`byte[]`).
- Session instantiation:
  ```csharp
  SessionOptions options = new SessionOptions();
  options.GraphOptimizationLevel = GraphOptimizationLevel.ORT_ENABLE_ALL;
  options.EnableMemoryPattern = true;
  options.AppendExecutionProvider_DML(0); // DirectML GPU
  InferenceSession session = new InferenceSession(decryptedBytes, options);
  ```
- Tensor signature detection:
  - Input name: queries `session.InputMetadata.Keys` (expects `"images"`).
  - Input dimensions: `[1, 3, H, W]` (default `H=W=640`).
  - Class name dictionary: reads custom metadata map `names` via regex `(\d+)\s*:\s*['"]([^'"]*)['"]`.
  - Class roles (`method_6`):
    - Head: matches `"head"`
    - Teammate: matches `"friend"`, `"team"`, `"ally"`, `"mate"`
    - Body/Enemy: matches `"person"`, `"body"`, `"enemy"`, `"player"`, `"opponent"`

#### B. Preprocessing & Tensor Creation (`YoloDetector::method_7`)
- Dedicated high-priority worker thread: `YOLO-Inference`.
- Frame cropping:
  - If `CenterCropEnabled` is true, crops center region (`width = DefaultInputSize`, `height = DefaultInputSize`).
- Format conversion & normalization:
  - `Cv2.CvtColor(mat, rgbMat, ColorConversionCodes.BGR2RGB)`
  - `Cv2.Resize(rgbMat, resizedMat, new OpenCvSharp.Size(inputWidth, inputHeight))`
  - `resizedMat.ConvertTo(floatMat, MatType.CV_32FC3, 1.0 / 255.0)`
  - `Cv2.Split(floatMat, out Mat[] channels)` (deinterleaves HWC to planar CHW)
- DenseTensor construction:
  - Formats into `DenseTensor<float>(data, new int[] { 1, 3, inputHeight, inputWidth })`.
  - Binds as `NamedOnnxValue.CreateFromTensor("images", tensor)`.
  - Calls `session.Run(new NamedOnnxValue[] { namedOnnxValue })`.

#### C. Postprocessing & Output Decoding (`YoloDetector::method_8`)
- Output shape: `[1, 4 + num_classes, num_anchors]` (e.g. `[1, 6, 8400]` for YOLOv8/YOLO11 with 2 classes).
- Anchor parsing:
  - For each column `i`: extracts `cx = out[0, 0, i]`, `cy = out[0, 1, i]`, `w = out[0, 2, i]`, `h = out[0, 3, i]`.
  - Scans class channels `j in [4 .. 4 + num_classes - 1]` to find highest score `score` and `classId`.
  - Confidence filter: `if (score < ConfidenceThreshold) continue;`
- Coordinate reconstruction:
  - `left = (cx - w / 2.0f) * scaleX + offsetX`
  - `top = (cy - h / 2.0f) * scaleY + offsetY`
  - `width = w * scaleX`, `height = h * scaleY`
- Non-Maximum Suppression (NMS):
  - Greedy IoU overlap suppression against `IouThreshold` (default ~0.40f).

#### D. Dynamic Object Tracking (`TrackedObject` & `YoloDetection`)
- Data structure:
  ```csharp
  public class TrackedObject {
      public int Id;
      public float CX, CY, W, H;
      public float RawCX, RawCY, RawW, RawH;
      public float Confidence;
      public float VelX, VelY;
      public int Age;
      public int MissedFrames;
      public bool IsTeammate;
      public bool IsHead;
      public int StillFrames;
      public float MotionEma;
      public bool IsStaticProp => StillFrames > 15 && MotionEma < 0.5f;
      public RectangleF GetPredictedRect();
      public RectangleF GetSmoothedRect();
  }
  ```
- **Velocity & Gap-Filling Prediction**:
  When camera capture (e.g. 120 - 240 FPS) outpaces model inference (e.g. 60 - 90 FPS), `GetPredictedRect()` extrapolates the bounding box using `CX + VelX * dt` and `CY + VelY * dt`. This prevents aim stutter and maintain continuous target tracking between neural network inference ticks.
- **Static Prop Rejection**:
  Monitors `StillFrames` and `MotionEma`. Objects that remain stationary across frames (e.g. mannequins, signs, wall posters) are tagged as `IsStaticProp` and ignored by the targeting engine.

#### E. Targeting & Aim Smoothing Algorithm (`lucifer_cv2.Form1::method_141`)
- **Target Selection**:
  - Computes Euclidean distance from crosshair `(screen_width / 2, screen_height / 2)` to target:
    `dist = Math.Sqrt((tx - cx)^2 + (ty - cy)^2)`
  - Rejects targets where `IsTeammate == true` or `IsStaticProp == true`.
  - Selects minimum distance target within field of view (FOV).
- **Target Offset Calculation**:
  - `yoloAimBiasPercent` and `get_HeadOffsetY()` interpolate the aim vertical coordinate between the body center of mass and the head:
    `target_y = body_cy - (body_h * 0.35f * aimBiasPercent)`
- **Aim Curves & Smoothing**:
  - Power curve: applies non-linear response `Math.Pow(normalized_dist, curve_exponent)` to provide gentle tracking near the crosshair and aggressive pull further away.
  - Directional damping: `aimReversalDamp` reduces stick deflection when the user reverses stick direction to prevent overshooting.
  - Profiles: Loaded from `speed_profiles.json` (`Flat`, `Flick Beast`, `Smooth`, `Linear`).
- **Snap / Flick Mode**:
  - If `flickEnabled` is active, instantly applies maximum deflection on the first frame of acquiring a new target.

#### F. Controller Emulation & Output Injection (`Form1::method_150`, `method_183`)
- `ViGEmClient.CreateXbox360Controller()` mounts a virtual Xbox 360 controller.
- Converts target pixel deltas `(delta_x, delta_y)` to normalized joystick axis values:
  - Range: `short.MinValue (-32768)` to `short.MaxValue (32767)`.
  - Axis: `Xbox360Axis.RightThumbX` (aim yaw) and `Xbox360Axis.RightThumbY` (aim pitch).
  - Triggers: `Xbox360Slider.RightTrigger` (auto-fire / triggerbot on target lock).
  - `controller.SubmitReport()`.
- System driver `HidHide` hides physical gamepad hardware IDs from the game process, routing all physical and synthetic inputs exclusively through the virtual ViGEm device.

---

## 2. Logic Chain

1. **Model Storage & Formats**:
   - *Observation*: `Vortx_buy\models\` contains 4 files with extension `.onnx.enc` and first 4 bytes `LCM1`.
   - *Observation*: String `#US` at token `0x102b11` reads `"No object model found. Place at least one .onnx (or .onnx.enc) model in: models"`.
   - *Logic*: The application supports both standard ONNX models and proprietary encrypted ONNX models (`.onnx.enc`) marked with header `LCM1`.

2. **Inference Execution Architecture**:
   - *Observation*: Project imports `Microsoft.ML.OnnxRuntime.dll` and ships `DirectML.dll`.
   - *Observation*: Method metadata confirms `SessionOptions.AppendExecutionProvider_DML(0)` is invoked before `InferenceSession` initialization.
   - *Logic*: The neural network inference does not rely on NVIDIA's proprietary CUDA toolkit; instead, it executes via DirectML, ensuring hardware acceleration across all DirectX 12 compatible GPUs (NVIDIA, AMD, Intel).

3. **Frame Capture Mechanism**:
   - *Observation*: `lucifer_cv2.Capture.DXGICapture` calls `D3D11CreateDevice`, `CreateDXGIFactory1`, and DirectX 11 Desktop Duplication interfaces.
   - *Observation*: `FlashCap.dll` is referenced with `CaptureDevices.EnumerateDescriptors()` and `OpenAsync`.
   - *Observation*: Companion executables `rm_re_fr\Vortx Stream.exe` (Chiaki) and `xlu\xlu.exe` (Electron/xCloud) are included.
   - *Logic*: The vision pipeline supports 4 distinct capture modes:
     a) Direct PC GPU Desktop Duplication (up to 240 FPS) for local PC gaming.
     b) FlashCap USB/Elgato video capture card for dual-PC stream capture.
     c) PlayStation remote stream capture via Chiaki backend.
     d) Xbox remote play / Cloud Gaming stream capture via Electron/WebRTC backend.

4. **Coordinate & Target Mapping**:
   - *Observation*: `YoloDetector` parses YOLO outputs and instantiates `TrackedObject`.
   - *Observation*: `Form1::method_141` processes `GetLatestDetections()`, calculates Euclidean distances, scales coordinates from model resolution (e.g. 640x640) to screen ROI, and writes to `ViGEmClient` axis values.
   - *Logic*: Detection coordinates are transformed from model space to screen space, smoothed via Kalman/EMA velocity filters, adjusted by vertical head-offset bias, and injected into the Windows input subsystem as physical Xbox 360 controller stick deflections.

---

## 3. Caveats

1. **Model Decryption Key Derivation**: The static encryption signature (`LCM1`) and AES crypto routines were confirmed in binary metadata, but the runtime session decryption key is bound to the license verification token retrieved from `luciferstore.store` / `lucifer-scriptss.com`. The models cannot be decrypted statically without the remote license challenge handshake.
2. **Predecessor Comparison**: The project contains remnants of its previous iteration (`Color Detection_Secure` in Downloads), which relied strictly on OpenCV HSV color segmentation (`Cv2.InRange`) and contour moments before transitioning to deep learning YOLO models in `Vortx.exe`.
3. **Execution Context**: This investigation was conducted completely read-only on the static files, zip streams, and portable executable metadata without running or activating the cheats or triggering third-party game anti-cheats.

---

## 4. Conclusion

The application located in `c:\Users\96655\Downloads\__VORTX STORE_ نسخة\VORTX STORE_ نسخة` is a high-performance, machine-learning-powered automated aim assist system ("Vortx // Lucifer CV2") targeting competitive first-person shooters (specifically *Call of Duty: Black Ops 6/7* and *Warzone*).

Key Architectural Findings:
1. **Machine Learning Pipeline**: Custom-trained YOLOv8 / YOLO11 models (in 320px, 640px, and 1280px variants) targeting player bodies, heads, and teammate differentiation.
2. **Model Security**: Models are distributed as AES-encrypted `.onnx.enc` binaries prefixed with the `LCM1` signature, decrypted exclusively in volatile memory at runtime.
3. **Inference Engine**: Microsoft ONNX Runtime backed by Microsoft DirectML for cross-vendor GPU acceleration (NVIDIA / AMD / Intel) with zero external CUDA dependencies.
4. **Computer Vision & Capture**: Ultra-low-latency screen acquisition via DXGI Desktop Duplication (supporting up to 240 FPS), augmented by UVC/Elgato capture card integration and console streaming client hooks (Chiaki for PS, xCloud for Xbox).
5. **Targeting & Smoothing**: Custom `TrackedObject` kinematic tracking with velocity prediction to interpolate between inference frames, static prop rejection, head-bias calculation, non-linear power response curves, and virtual Xbox 360 controller thumbstick injection via ViGEmBus and HidHide.

---

## 5. Verification Method

To independently verify these findings, run the following inspection commands in PowerShell:

### 1. Verify Encrypted Model Files & Headers:
```powershell
$base = (Get-ChildItem -Path "c:\Users\96655\Downloads\__VORTX STORE_ نسخة")[0].FullName
$models = Join-Path $base "Vortx (1)\Vortx\Vortx_buy\models"
Get-ChildItem -Path $models | ForEach-Object {
    $bytes = [System.IO.File]::ReadAllBytes($_.FullName)
    $magic = [System.Text.Encoding]::ASCII.GetString($bytes[0..3])
    [PSCustomObject]@{ Name = $_.Name; Length = $_.Length; Header = $magic }
}
```
*Expected Output*: 4 files (`Lucifer-Head-only.onnx.enc`, `LuciferBestV2-5.onnx.enc`, `LuciferBestV2.onnx.enc`, `LuciferStrongestV3.onnx.enc`), each starting with header `LCM1`.

### 2. Verify DirectML & ONNX Runtime Assembly References:
```powershell
$zip = [System.IO.Compression.ZipFile]::OpenRead('c:\Users\96655\Downloads\__VORTX STORE_ نسخة.zip')
$entry = $zip.Entries | Where-Object { $_.FullName -like '*Vortx.exe' }
$ms = New-Object System.IO.MemoryStream
$s = $entry.Open(); $s.CopyTo($ms); $s.Dispose(); $zip.Dispose()
$ms.Position = 0
$pe = New-Object System.Reflection.PortableExecutable.PEReader($ms)
$mr = [System.Reflection.Metadata.PEReaderExtensions]::GetMetadataReader($pe)
foreach ($h in $mr.MemberReferences) {
    $m = $mr.GetMemberReference($h)
    $name = $mr.GetString($m.Name)
    if ($name -match 'AppendExecutionProvider_DML|CreateXbox360Controller|D3D11CreateDevice') {
        Write-Host "Verified Reference: $name"
    }
}
```
*Expected Output*: References to `AppendExecutionProvider_DML`, `CreateXbox360Controller`, and `D3D11CreateDevice`.

### 3. Verify Target Classes & Model Presets in Metadata:
```powershell
python -c "
import zipfile, re
with zipfile.ZipFile('c:/Users/96655/Downloads/__VORTX STORE_ نسخة.zip', 'r') as z:
    for n in z.namelist():
        if n.endswith('Vortx.exe'): data = z.read(n); break
for kw in [b'VORTX V3 HD', b'AIO HEADS', b'WARZONE 50k', b'yolo11m', b'yolov8s']:
    print(kw.decode(), 'found:', kw in data)
"
```
*Expected Output*: All keywords evaluate to `True`.
