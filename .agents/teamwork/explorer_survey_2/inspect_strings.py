import re

def inspect_strings(path, name):
    print(f"\n==================== {name} ====================")
    with open(path, 'rb') as f:
        data = f.read()

    # Find ascii strings length >= 6
    ascii_strings = [s.decode('ascii', errors='ignore') for s in re.findall(rb'[ -~]{6,}', data)]
    # Find utf-16le strings
    utf16_strings = [s.decode('utf-16le', errors='ignore') for s in re.findall(rb'(?:[\x20-\x7e]\x00){6,}', data)]

    all_strings = ascii_strings + utf16_strings

    print(f"Total extracted strings: {len(all_strings)}")

    # Look for command-line flags (starting with -- or -)
    flags = set([s for s in all_strings if s.startswith('--') or (s.startswith('-') and len(s) < 15 and not s.startswith('---'))])
    print(f"Sample flags ({len(flags)}): {list(flags)[:15]}")

    # Look for model/aim/onnx/yolo/detection/capture strings
    ai_strings = set([s for s in all_strings if any(w in s.lower() for w in ['model', 'onnx', 'yolo', 'detect', 'capture', 'aim', 'target', 'smooth', 'fov', 'recoil', 'screen', 'trigger', 'bone', 'confidence'])])
    print(f"AI/Aim/Detection strings ({len(ai_strings)}): {list(ai_strings)[:20]}")

    # Look for net/http/url/socket/server/port
    net_strings = set([s for s in all_strings if any(w in s.lower() for w in ['http', 'ws://', 'port', 'connect', 'listen', 'session', 'auth']) and len(s) < 100])
    print(f"Network/IPC strings ({len(net_strings)}): {list(net_strings)[:20]}")

inspect_strings(r"c:\Users\96655\Downloads\__VORTX STORE_ نسخة\‏‏VORTX STORE_ نسخة\Vortx (1)\Vortx\Vortx_buy\rm_re_fr\Vortx Stream.exe", "Vortx Stream.exe")
inspect_strings(r"c:\Users\96655\Downloads\__VORTX STORE_ نسخة\‏‏VORTX STORE_ نسخة\Vortx (1)\Vortx\Vortx_buy\rm_re_fr\lu.exe", "lu.exe")
