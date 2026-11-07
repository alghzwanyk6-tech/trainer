# -*- coding: utf-8 -*-
import os

targets = [
    r"c:\Users\96655\Downloads\__VORTX STORE_ نسخة\VORTX STORE_ نسخة\TECHNICAL_ANALYSIS_REPORT.md",
    r"c:\Users\96655\Downloads\__VORTX STORE_ نسخة\‏‏VORTX STORE_ نسخة\Vortx (1)\Vortx\Vortx_buy\TECHNICAL_ANALYSIS_REPORT.md",
    r"c:\Users\96655\Downloads\__VORTX STORE_ نسخة\‏‏VORTX STORE_ نسخة\TECHNICAL_ANALYSIS_REPORT.md",
    r"c:\Users\96655\ui\aim_trainer_project\.agents\teamwork\orchestrator\TECHNICAL_ANALYSIS_REPORT.md",
    r"c:\Users\96655\ui\aim_trainer_project\.agents\teamwork\worker_m4_1\TECHNICAL_ANALYSIS_REPORT.md"
]

print("=== VERIFYING DELIVERABLES ===")
for t in targets:
    if os.path.exists(t):
        sz = os.path.getsize(t)
        print(f"[FOUND] {t} ({sz} bytes)")
        assert sz > 10240, f"File {t} is below 10 KB threshold!"
    else:
        print(f"[MISSING] {t}")
        raise FileNotFoundError(f"Missing required deliverable: {t}")

print("\n=== VERIFYING CONTENT KEYWORDS ===")
orch_report = r"c:\Users\96655\ui\aim_trainer_project\.agents\teamwork\orchestrator\TECHNICAL_ANALYSIS_REPORT.md"
with open(orch_report, "r", encoding="utf-8") as f:
    content = f.read()

checks = [
    "LCM1",
    "DirectML",
    "ViGEmBus",
    "HidHide",
    "ChiakiFrameShare",
    "Trojan:Win32/Wacatac.B!ml",
    "TrackedObject",
    "yolo11m",
    "9003",
    "5218",
    "CaptureManager.cs",
    "OpenCvSharp"
]

for kw in checks:
    assert kw in content, f"Missing keyword '{kw}' in report!"
    print(f"[MATCH] Keyword '{kw}' verified in report.")

print("\nALL VERIFICATIONS PASSED SUCCESSFULLY.")
