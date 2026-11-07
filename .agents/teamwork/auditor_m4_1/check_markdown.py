import re

report_path = r"c:\Users\96655\ui\aim_trainer_project\.agents\teamwork\orchestrator\TECHNICAL_ANALYSIS_REPORT.md"
with open(report_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

fence_lines = []
for idx, line in enumerate(lines, 1):
    # Match markdown code fences (``` or ~~~)
    m = re.match(r"^\s*(`{3,}|~{3,})", line)
    if m:
        fence_lines.append((idx, line.strip()))

print(f"Total fences found: {len(fence_lines)}")
for idx, text in fence_lines:
    print(f"Line {idx:3d}: {text}")

if len(fence_lines) % 2 != 0:
    print("ERROR: Odd number of code fences! Unclosed fence exists.")
else:
    print("SUCCESS: Code fences are perfectly balanced in pairs!")
