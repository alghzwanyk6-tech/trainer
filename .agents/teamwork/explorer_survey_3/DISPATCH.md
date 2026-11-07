# Dispatch Assignment - Explorer 3 (Machine Learning & Advanced Assets Analysis)

**Target Project Directory**: `c:\Users\96655\Downloads\__VORTX STORE_ نسخة\VORTX STORE_ نسخة`
**Original Request**: `c:\Users\96655\ui\aim_trainer_project\.agents\teamwork\ORIGINAL_REQUEST.md`
**Your Working Directory**: `c:\Users\96655\ui\aim_trainer_project\.agents\teamwork\explorer_survey_3\`

## Objectives:
1. Search for and inventory all machine learning assets, model files (.onnx, .pt, .pth, .engine, .tflite, .weights, etc.), dataset files, and config files.
2. Analyze how models are loaded, preprocessed, inferred, and postprocessed in the codebase.
3. Identify detection targets (e.g. object classes, keypoints), computer vision pipelines (capture, preprocessing, inference, screen coordinates mapping), and hardware acceleration requirements.
4. Document all findings, model architectures, inputs/outputs, and integration points in `handoff.md` in your working directory.

## 2026-11-06T00:45:07Z
From: 3f6ce2e1-b5dd-4508-8380-7cee0721f57a
Priority: MESSAGE_PRIORITY_HIGH
Content:
You are Explorer 3 (Machine Learning & Advanced Assets Explorer).
Your Working Directory: c:\Users\96655\ui\aim_trainer_project\.agents\teamwork\explorer_survey_3\
Original Request Path: c:\Users\96655\ui\aim_trainer_project\.agents\teamwork\ORIGINAL_REQUEST.md
Target Directory to Inspect: c:\Users\96655\Downloads\__VORTX STORE_ نسخة\VORTX STORE_ نسخة

MANDATORY INSTRUCTIONS:
1. First read ORIGINAL_REQUEST.md and your DISPATCH.md at c:\Users\96655\ui\aim_trainer_project\.agents\teamwork\explorer_survey_3\DISPATCH.md.
2. Initialize BRIEFING.md and progress.md in your working directory. Keep progress.md updated after every step with 'Last visited: [timestamp]'.
3. Discover, inspect, and analyze all machine learning assets and related algorithms:
   - Identify model files (.onnx, .pt, .pth, .engine, .tflite, .weights, etc.), model weights, configs, metadata.
   - Analyze inference engines (ONNX Runtime, PyTorch, TensorRT, OpenCV DNN, etc.).
   - Analyze computer vision pipelines: frame capture mechanism (DXGI, BitBlt, Windows Graphics Capture, mss, etc.), preprocessing (scaling, normalization, letterboxing), inference, postprocessing (NMS, confidence filtering), target calculation, coordinate transformation, smoothing/aiming logic.
   - Detect what classes/objects the models target and hardware acceleration dependencies (CUDA, DirectML, CPU).
4. Provide verified code references, model metadata, tensor shapes, and pipeline architecture.
5. Write a comprehensive, self-contained handoff.md in your working directory (Observation, Logic Chain, Caveats, Conclusion, Verification Method).
6. When done, use send_message to report completion to the orchestrator.
Do NOT modify or write any files outside your working directory! You are read-only regarding the target directory.
