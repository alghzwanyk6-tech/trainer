import os
from collections import defaultdict

root = r'c:\Users\96655\Downloads\__VORTX STORE_ نسخة'
vortx_buy = None
for r, d, f in os.walk(root):
    if os.path.basename(r) == 'Vortx_buy':
        vortx_buy = r
        break

print(f"Vortx_buy path: {vortx_buy}")
total_files = 0
total_dirs = 0
total_size = 0
ext_counts = defaultdict(int)
ext_sizes = defaultdict(int)

for r, d, f in os.walk(vortx_buy):
    total_dirs += len(d)
    for file in f:
        total_files += 1
        fp = os.path.join(r, file)
        try:
            sz = os.path.getsize(fp)
        except Exception as e:
            sz = 0
        total_size += sz
        ext = os.path.splitext(file)[1].lower()
        ext_counts[ext] += 1
        ext_sizes[ext] += sz

print(f"Total Files: {total_files}")
print(f"Total Dirs: {total_dirs}")
print(f"Total Size: {total_size} bytes ({total_size / (1024*1024):.2f} MB)")
print("--- Extension Breakdown ---")
for ext, cnt in sorted(ext_counts.items(), key=lambda x: x[1], reverse=True)[:16]:
    lbl = ext if ext else '(no extension)'
    sz_mb = ext_sizes[ext] / (1024*1024)
    pct = (ext_sizes[ext] / total_size) * 100
    print(f"{lbl:16}: Count={cnt:4d}, Size={sz_mb:7.2f} MB ({pct:5.2f}%)")
