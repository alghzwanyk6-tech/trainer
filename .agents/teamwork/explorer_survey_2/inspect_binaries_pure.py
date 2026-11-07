import os
import re

files = [
    r"c:\Users\96655\Downloads\__VORTX STORE_ نسخة\‏‏VORTX STORE_ نسخة\Vortx (1)\Vortx\Vortx_buy\rm_re_fr\Vortx Stream.exe",
    r"c:\Users\96655\Downloads\__VORTX STORE_ نسخة\‏‏VORTX STORE_ نسخة\Vortx (1)\Vortx\Vortx_buy\rm_re_fr\lu.exe",
]

def analyze_binary(path):
    print(f"\n==================== {os.path.basename(path)} ====================")
    size = os.path.getsize(path)
    print(f"File size: {size:,} bytes")
    with open(path, 'rb') as f:
        data = f.read()

    # Search for version info strings (like ProductName, FileDescription, OriginalFilename, LegalCopyright)
    for field in [b'ProductName', b'FileDescription', b'OriginalFilename', b'ProductVersion', b'CompanyName', b'Comments']:
        idx = data.find(field)
        if idx != -1:
            # Look ahead for utf-16 or ascii string
            sub = data[idx:idx+150]
            # Try to decode utf-16le
            try:
                # filter null bytes
                cleaned = sub.replace(b'\x00\x00', b'|').replace(b'\x00', b'')
                print(f"  Field {field.decode()}: {cleaned[:80]}")
            except Exception as e:
                pass

    # Search for specific interesting strings: chiaki, stream, playstation, psn, lucifer, onnx, yolo, aim, etc.
    patterns = [
        (rb'chiaki', 'Chiaki references'),
        (rb'lucifer', 'Lucifer references'),
        (rb'vortx', 'Vortx references'),
        (rb'onnx', 'ONNX references'),
        (rb'cuda', 'CUDA references'),
        (rb'directml', 'DirectML references'),
        (rb'vigem', 'ViGEm references'),
        (rb'hidhide', 'HidHide references'),
        (rb'ps4|ps5|playstation', 'PlayStation references'),
        (rb'github\.com\/[a-zA-Z0-9_\-\/]+', 'GitHub URLs'),
    ]

    for pat, label in patterns:
        matches = set(re.findall(pat, data, re.IGNORECASE))
        if matches:
            decoded = [m.decode('latin1', errors='ignore') for m in list(matches)[:10]]
            print(f"  {label} ({len(matches)}): {decoded}")

for fp in files:
    analyze_binary(fp)
