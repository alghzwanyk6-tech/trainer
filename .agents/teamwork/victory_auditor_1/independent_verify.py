import os
import hashlib
import json

target_root = r"c:\Users\96655\Downloads\__VORTX STORE_ نسخة"

total_files = 0
total_dirs = 0
total_size = 0
extensions = {}
pe_files = []
enc_models = []
bat_files = []
ps1_files = []

for root, dirs, files in os.walk(target_root):
    total_dirs += len(dirs)
    for f in files:
        total_files += 1
        fp = os.path.join(root, f)
        try:
            sz = os.path.getsize(fp)
            total_size += sz
            ext = os.path.splitext(f)[1].lower()
            extensions[ext] = extensions.get(ext, 0) + 1
            if ext in ['.exe', '.dll']:
                pe_files.append((fp, sz))
            elif ext == '.enc' or '.onnx' in f.lower():
                enc_models.append((fp, sz))
            elif ext == '.bat':
                bat_files.append((fp, sz))
            elif ext == '.ps1':
                ps1_files.append((fp, sz))
        except Exception as e:
            pass

print(f"Total directories walked: {total_dirs}")
print(f"Total files found: {total_files}")
print(f"Total size: {total_size:,} bytes ({total_size / (1024**3):.4f} GB)")
print("\nTop 20 extensions:")
for ext, count in sorted(extensions.items(), key=lambda x: x[1], reverse=True)[:20]:
    name = ext if ext else "(no extension)"
    print(f"  {name:15}: {count}")

print(f"\nTotal PE binaries (.exe, .dll): {len(pe_files)}")
print(f"Total models/enc files: {len(enc_models)}")
for m, s in enc_models:
    print(f"  Model: {m} ({s:,} bytes)")

print(f"\nScripts found:")
for b, s in bat_files:
    print(f"  Batch: {b} ({s:,} bytes)")
for p, s in ps1_files:
    print(f"  PowerShell: {p} ({s:,} bytes)")
