import os
import re

report_path = r"c:\Users\96655\ui\aim_trainer_project\.agents\teamwork\orchestrator\TECHNICAL_ANALYSIS_REPORT.md"
with open(report_path, "r", encoding="utf-8") as f:
    text = f.read()

# Check math delimiters ($...$ and $$...$$)
inline_math = re.findall(r'(?<!\$)\$(?!\$)(.*?)(?<!\$)\$(?!\$)', text)
block_math = re.findall(r'\$\$(.*?)\$\$', text, re.DOTALL)
print(f"Found {len(inline_math)} inline math expressions and {len(block_math)} block math expressions.")

# Check tables
table_blocks = re.findall(r'(\|[^\n]+\|\n\|[-:| ]+\|\n(?:\|[^\n]+\|\n*)+)', text)
print(f"Found {len(table_blocks)} markdown tables.")
for i, tbl in enumerate(table_blocks, 1):
    rows = tbl.strip().split("\n")
    header_cols = len([c for c in rows[0].split("|")[1:-1]])
    sep_cols = len([c for c in rows[1].split("|")[1:-1]])
    print(f"  Table {i}: {header_cols} columns, {len(rows)-2} data rows")
    assert header_cols == sep_cols, f"Table {i} column mismatch: header {header_cols} != sep {sep_cols}"

print("All markdown tables are structurally valid!")
