import os
import sys
import struct
import json
import zipfile

print("=== VICTORY AUDITOR INDEPENDENT EXECUTION OF SECTION 10 VERIFICATION METHODS ===")

# 10.1 Unicode Path & Directory Hierarchy
root = r"c:\Users\96655\Downloads\__VORTX STORE_ نسخة"
vortx_buy = None
for r, dirs, files in os.walk(root):
    if os.path.basename(r) == "Vortx_buy":
        vortx_buy = r
        break

assert vortx_buy is not None, "Vortx_buy directory not found!"
print(f"[PASS 10.1] Resolved Payload Directory: {vortx_buy}")
subdirs = [d for d in os.listdir(vortx_buy) if os.path.isdir(os.path.join(vortx_buy, d))]
print(f"            Subdirectories: {subdirs}")

# 10.2 Verify Encrypted Model Files & LCM1 Magic Header
models_dir = os.path.join(vortx_buy, "models")
enc_files = [f for f in os.listdir(models_dir) if f.endswith(".enc")]
print(f"[PASS 10.2] Found {len(enc_files)} .enc files in models/:")
for ef in enc_files:
    fp = os.path.join(models_dir, ef)
    with open(fp, "rb") as f:
        magic = f.read(4)
    sz = os.path.getsize(fp)
    assert magic == b"LCM1", f"Model {ef} header {magic} != LCM1"
    print(f"            {ef} ({sz:,} bytes) -> Magic: {magic.decode('ascii')}")

# 10.4 Verify Presence of Quarantined Vortx.exe in Original Archive
zip_path = r"c:\Users\96655\Downloads\__VORTX STORE_ نسخة.zip"
assert os.path.exists(zip_path), f"Zip archive {zip_path} not found"
with zipfile.ZipFile(zip_path, 'r') as zf:
    vortx_entries = [e for e in zf.infolist() if e.filename.endswith("Vortx.exe")]
    assert len(vortx_entries) > 0, "Vortx.exe not found in zip archive"
    for e in vortx_entries:
        print(f"[PASS 10.4] Vortx.exe in zip: {e.filename} (Uncompressed: {e.file_size:,} bytes, Compressed: {e.compress_size:,} bytes)")
        assert e.file_size == 6599168, f"Vortx.exe size mismatch: {e.file_size}"

# 10.5 Verify DirectML and Gamepad Assembly References in Core Engine
stream_exe = os.path.join(vortx_buy, "rm_re_fr", "Vortx Stream.exe")
assert os.path.exists(stream_exe), f"{stream_exe} missing"
with open(stream_exe, "rb") as f:
    stream_bytes = f.read()

required_symbols = [
    b"AppendExecutionProvider_DML",
    b"CreateXbox360Controller",
    b"D3D11CreateDevice",
    b"SubmitReport"
]
for sym in required_symbols:
    assert sym in stream_bytes, f"Symbol {sym.decode('latin1')} missing from Vortx Stream.exe"
print(f"[PASS 10.5] All required symbols found in Vortx Stream.exe: {[s.decode('latin1') for s in required_symbols]}")

# 10.6 Verify Electron Package Metadata in Xbox Subsystem
asar_path = os.path.join(vortx_buy, "xlu", "resources", "app.asar")
assert os.path.exists(asar_path), f"{asar_path} missing"
with open(asar_path, "rb") as f:
    header_raw = f.read(16)
    magic, total_size, size2, json_len = struct.unpack("<IIII", header_raw)
    header_json = json.loads(f.read(json_len).decode("utf-8"))
    data_offset = (16 + json_len + 3) & ~3
    pkg_entry = header_json["files"]["package.json"]
    f.seek(data_offset + int(pkg_entry["offset"]))
    pkg_data = json.loads(f.read(int(pkg_entry["size"])).decode("utf-8"))

print(f"[PASS 10.6] Extracted package.json from app.asar:")
print(f"            Name: {pkg_data.get('name')}")
print(f"            Product: {pkg_data.get('productName')}")
print(f"            Version: {pkg_data.get('version')}")
print(f"            Main: {pkg_data.get('main')}")
print(f"            Dependencies: {list(pkg_data.get('dependencies', {}).keys())}")

print("\n=== ALL INDEPENDENT SECTION 10 VERIFICATIONS CONFIRMED! ===")
