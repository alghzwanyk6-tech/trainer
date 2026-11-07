import os

root = r'c:\Users\96655\Downloads\__VORTX STORE_ نسخة'
vortx_buy = None
for r, d, f in os.walk(root):
    if os.path.basename(r) == 'Vortx_buy':
        vortx_buy = r
        break

stream_exe = os.path.join(vortx_buy, 'rm_re_fr', 'Vortx Stream.exe')
with open(stream_exe, 'rb') as f:
    stream_bytes = f.read()

checks_stream = [
    'DirectML',
    'AppendExecutionProvider_DML',
    'CreateXbox360Controller',
    'SubmitReport',
    'HidHide',
    'TrackedObject',
    'YoloDetector',
    'yoloAimBiasPercent',
    'aimReversalDamp',
    'ChiakiFrameShare',
    'urscript.shop',
    'luciferstore.store'
]

print("--- Vortx Stream.exe (ASCII and UTF-16LE) ---")
for c in checks_stream:
    c_ascii = c.encode('ascii')
    c_u16 = c.encode('utf-16le')
    found_ascii = c_ascii in stream_bytes
    found_u16 = c_u16 in stream_bytes
    print(f"  {c}: ASCII={found_ascii}, UTF16={found_u16}")

asar_path = os.path.join(vortx_buy, 'xlu', 'resources', 'app.asar')
with open(asar_path, 'rb') as f:
    asar_bytes = f.read(25000000)

checks_asar = [
    'greenlight-desktop',
    'Lucifer',
    '5218',
    'microsoft.com/link',
    'xal-node',
    'تسجيل الدخول'
]

print("--- app.asar (UTF-8) ---")
for c in checks_asar:
    c_utf8 = c.encode('utf-8')
    print(f"  {c}: UTF8={c_utf8 in asar_bytes}")
