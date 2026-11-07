import re

path = r"c:\Users\96655\Downloads\__VORTX STORE_ نسخة\‏‏VORTX STORE_ نسخة\Vortx (1)\Vortx\Vortx_buy\rm_re_fr\Vortx Stream.exe"

with open(path, 'rb') as f:
    data = f.read()

ident_pattern = re.compile(rb'[A-Za-z_][A-Za-z0-9_]{2,}')
identifiers = [i.decode('ascii', errors='ignore') for i in ident_pattern.findall(data)]

# Find all items matching lucifer_cv2
lucifer_items = sorted(set([i for i in identifiers if 'lucifer_cv2' in i or any(x in i.lower() for x in ['aimpanel', 'colorpanel', 'gamepanel', 'licensemanager', 'psnbrowser', 'vigem', 'hidhide'])]))
print("--- Lucifer Types and Classes ---")
for x in lucifer_items:
    print(x)

# Find all string literals (between quotes or in #US heap)
# In .NET, #US stream contains user strings
us_pos = data.find(b'#US\x00')
print("\n#US stream pos:", us_pos)
if us_pos != -1:
    # Read next 100kb and extract utf-16 strings
    us_data = data[us_pos:us_pos+200000]
    # In #US, strings are stored with length prefix in UTF-16LE
    # Let's extract utf-16le strings >= 4 chars
    us_strings = [s.decode('utf-16le', errors='ignore') for s in re.findall(rb'(?:[\x20-\x7e]\x00){4,}', us_data)]
    print(f"Total #US user strings: {len(us_strings)}")
    # Print interesting strings
    print("\n--- User Strings (Auth, Endpoints, Configs) ---")
    for s in us_strings:
        if any(w in s.lower() for w in ['http', 'api', 'key', 'token', 'license', 'model', 'onnx', 'stream', 'psn', 'xbox', 'auth', 'port', 'password', 'discord']):
            print(" ", s)
