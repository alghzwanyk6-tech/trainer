import os
import sys
import glob
import json
import zipfile
import hashlib
import struct

print("=== STARTING INDEPENDENT FORENSIC AUDIT ===")

root_raw = r"c:\Users\96655\Downloads\__VORTX STORE_ نسخة"
print(f"Testing root existence: {os.path.exists(root_raw)}")

# 1. Resolve actual payload directory
resolved_payload = None
for dirpath, dirnames, filenames in os.walk(root_raw):
    if "Vortx_buy" in dirnames:
        resolved_payload = os.path.join(dirpath, "Vortx_buy")
        break

print(f"Resolved Payload Directory: {resolved_payload}")
if not resolved_payload or not os.path.exists(resolved_payload):
    print("ERROR: Could not locate Vortx_buy directory!")
    sys.exit(1)

# Check RLM characters in parent
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(resolved_payload)))
print(f"Second level folder repr: {repr(os.path.basename(parent_dir))}")
contains_rlm = "\u200f" in os.path.basename(parent_dir)
print(f"Contains Unicode RLM (\\u200F): {contains_rlm}")

# 2. Count files, directories, size, extensions
total_files = 0
total_dirs = 0
total_bytes = 0
ext_counts = {}

for root, dirs, files in os.walk(resolved_payload):
    total_dirs += len(dirs)
    for f in files:
        total_files += 1
        fp = os.path.join(root, f)
        try:
            sz = os.path.getsize(fp)
            total_bytes += sz
            ext = os.path.splitext(f)[1].lower()
            if not ext:
                ext = "(no extension)"
            ext_counts[ext] = ext_counts.get(ext, 0) + 1
        except Exception as e:
            pass

print(f"Total Files in Vortx_buy: {total_files}")
print(f"Total Dirs in Vortx_buy: {total_dirs}")
print(f"Total Bytes in Vortx_buy: {total_bytes} ({total_bytes / (1024*1024):.2f} MB)")
print("Top Extensions:")
for ext, count in sorted(ext_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
    print(f"  {ext}: {count}")

# 3. Verify Models
models_dir = os.path.join(resolved_payload, "models")
print(f"Models directory exists: {os.path.exists(models_dir)}")
expected_models = [
    ("Lucifer-Head-only.onnx.enc", 10604564),
    ("LuciferBestV2-5.onnx.enc", 10569988),
    ("LuciferBestV2.onnx.enc", 10569988),
    ("LuciferStrongestV3.onnx.enc", 10457380)
]
for mname, exp_size in expected_models:
    mp = os.path.join(models_dir, mname)
    if os.path.exists(mp):
        actual_size = os.path.getsize(mp)
        with open(mp, "rb") as f:
            header = f.read(4)
        print(f"MODEL {mname}: Size={actual_size} (Expected={exp_size}, Match={actual_size==exp_size}), Header={header}")
    else:
        print(f"MODEL {mname}: MISSING")

# 4. Verify Key Executables
executables = [
    (r"rm_re_fr\Vortx Stream.exe", 7665152),
    (r"rm_re_fr\lu.exe", 6139904),
    (r"xlu\xlu.exe", 227062784),
    (r"Very important to install\NDP48-x86-x64-AllOS-ENU.exe", 121346568),
    (r"Very important to install\ViGEmBus_1.22.0_x64_x86_arm64.exe", 6278576),
    (r"Very important to install\HidHide_1.5.230_x64.exe", 8078016)
]
for rel, exp_size in executables:
    ep = os.path.join(resolved_payload, rel)
    if os.path.exists(ep):
        actual_size = os.path.getsize(ep)
        print(f"EXE {rel}: Size={actual_size} (Expected={exp_size}, Match={actual_size==exp_size})")
    else:
        print(f"EXE {rel}: MISSING")

# 5. Check Original Zip for Vortx.exe
zip_path = r"c:\Users\96655\Downloads\__VORTX STORE_ نسخة.zip"
print(f"Zip archive exists: {os.path.exists(zip_path)}")
if os.path.exists(zip_path):
    with zipfile.ZipFile(zip_path, "r") as z:
        vortx_entries = [e for e in z.infolist() if e.filename.endswith("Vortx.exe")]
        for e in vortx_entries:
            data = z.read(e.filename)
            h = hashlib.sha256(data).hexdigest()
            print(f"ZIP Entry: {e.filename}, UncompressedSize: {e.file_size}, SHA256: {h}")

# 6. Verify Scripts
bat_file = os.path.join(resolved_payload, "التعــــــريفات.bat")
ps1_file = os.path.join(resolved_payload, "VortxRequirements.ps1")
print(f"التعــــــريفات.bat exists: {os.path.exists(bat_file)}")
if os.path.exists(bat_file):
    with open(bat_file, "r", encoding="latin-1", errors="ignore") as f:
        bat_content = f.read()
    print("التعــــــريفات.bat content snippets:")
    print("  Contains Add-MpPreference:", "Add-MpPreference" in bat_content)
    print("  Contains advfirewall:", "advfirewall" in bat_content)
    print("  Contains w32tm:", "w32tm" in bat_content)

print(f"VortxRequirements.ps1 exists: {os.path.exists(ps1_file)}")
if os.path.exists(ps1_file):
    with open(ps1_file, "r", encoding="utf-8", errors="ignore") as f:
        ps1_content = f.read()
    print("VortxRequirements.ps1 snippets:")
    print("  Contains 461808 (.NET 4.7.2):", "461808" in ps1_content)
    print("  Contains ViGEmBus:", "ViGEmBus" in ps1_content)
    print("  Contains HidHide:", "HidHide" in ps1_content)
    print("  Contains F3017226 (WebView2):", "F3017226" in ps1_content)

print("=== INDEPENDENT FORENSIC VERIFICATION INITIAL RUN COMPLETE ===")
