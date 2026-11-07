import re

path = r"c:\Users\96655\Downloads\__VORTX STORE_ نسخة\‏‏VORTX STORE_ نسخة\Vortx (1)\Vortx\Vortx_buy\rm_re_fr\Vortx Stream.exe"

with open(path, 'rb') as f:
    data = f.read()

# Extract all ASCII and UTF-16LE strings >= 5 chars
ascii_s = [s.decode('ascii', errors='ignore') for s in re.findall(rb'[ -~]{5,}', data)]
utf16_s = [s.decode('utf-16le', errors='ignore') for s in re.findall(rb'(?:[\x20-\x7e]\x00){5,}', data)]
all_s = sorted(set(ascii_s + utf16_s))

print(f"Total unique strings: {len(all_s)}")

categories = {
    "License & Auth": [s for s in all_s if any(k in s.lower() for k in ['license', 'heartbeat', 'activate', 'token', 'auth', 'deviceid', 'hwid', 'subscription', 'expires'])],
    "Network & API": [s for s in all_s if any(k in s.lower() for k in ['http://', 'https://', '127.0.0.1', 'localhost', ':900', 'api/', 'rest', 'endpoint', 'postasync', 'getasync'])],
    "Model & AI": [s for s in all_s if any(k in s.lower() for k in ['.enc', '.onnx', 'model', 'inference', 'directml', 'tensor', 'detection', 'confidence', 'fov', 'recoil', 'aimbot', 'head-only', 'luciferbest'])],
    "Streaming & Remote Play": [s for s in all_s if any(k in s.lower() for k in ['chiaki', 'psn', 'ps4', 'ps5', 'xbox', 'xcloud', 'dxgi', 'flashcap', 'webrtc', 'duplication'])],
    "Gamepad & Input": [s for s in all_s if any(k in s.lower() for k in ['vigem', 'hidhide', 'xinput', 'controller', 'joystick', 'trigger', 'stick', 'deadzone'])]
}

for cat, lst in categories.items():
    print(f"\n==================== {cat} ({len(lst)}) ====================")
    for s in lst[:40]:
        print(" ", s)
    if len(lst) > 40:
        print(f"  ... and {len(lst) - 40} more")
