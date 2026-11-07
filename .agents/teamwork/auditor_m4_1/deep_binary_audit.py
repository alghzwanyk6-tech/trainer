import os
import sys

root_raw = r"c:\Users\96655\Downloads\__VORTX STORE_ نسخة"
resolved_payload = None
for dirpath, dirnames, filenames in os.walk(root_raw):
    if "Vortx_buy" in dirnames:
        resolved_payload = os.path.join(dirpath, "Vortx_buy")
        break

print(f"Target payload: {resolved_payload}")

# 1. Vortx Stream.exe inspection
stream_exe = os.path.join(resolved_payload, r"rm_re_fr\Vortx Stream.exe")
if os.path.exists(stream_exe):
    with open(stream_exe, "rb") as f:
        data = f.read()
    print(f"Vortx Stream.exe read {len(data)} bytes.")
    stream_keywords = [
        b"AppendExecutionProvider_DML",
        b"CreateXbox360Controller",
        b"TrackedObject",
        b"CaptureManager",
        b"YoloDetector",
        b"LicenseManager",
        b"DirectML",
        b"ViGEmClient",
        b"HidHide",
        b"OpenCvSharp",
        b"ChiakiFrameShare",
        b"urscript.shop",
        b"luciferstore.store"
    ]
    for kw in stream_keywords:
        found = kw in data
        print(f"  Vortx Stream.exe has '{kw.decode('utf-8', errors='ignore')}': {found}")
else:
    print("Vortx Stream.exe NOT FOUND")

# 2. lu.exe inspection
lu_exe = os.path.join(resolved_payload, r"rm_re_fr\lu.exe")
if os.path.exists(lu_exe):
    with open(lu_exe, "rb") as f:
        data = f.read()
    print(f"lu.exe read {len(data)} bytes.")
    lu_keywords = [
        b"chiaki",
        b"9003",
        b"ChiakiFrameShare",
        b"SDL",
        b"Qt",
        b"avcodec"
    ]
    for kw in lu_keywords:
        found = kw.lower() in data.lower()
        print(f"  lu.exe has '{kw.decode('utf-8', errors='ignore')}': {found}")
else:
    print("lu.exe NOT FOUND")

# 3. app.asar inspection
asar_file = os.path.join(resolved_payload, r"xlu\resources\app.asar")
if os.path.exists(asar_file):
    with open(asar_file, "rb") as f:
        data = f.read()
    print(f"app.asar read {len(data)} bytes.")
    asar_keywords = [
        b"greenlight-desktop",
        b"Lucifer",
        b"5218",
        b"microsoft.com/link",
        b"koffi",
        b"xal-node"
    ]
    for kw in asar_keywords:
        found = kw.lower() in data.lower()
        print(f"  app.asar has '{kw.decode('utf-8', errors='ignore')}': {found}")
else:
    print("app.asar NOT FOUND")
