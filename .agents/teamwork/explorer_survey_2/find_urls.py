import re

fp = r"c:\Users\96655\Downloads\__VORTX STORE_ نسخة\‏‏VORTX STORE_ نسخة\Vortx (1)\Vortx\Vortx_buy\rm_re_fr\Vortx Stream.exe"
with open(fp, 'rb') as f:
    data = f.read()

target = 'https://'.encode('utf-16le')
idx = 0
while True:
    idx = data.find(target, idx)
    if idx == -1:
        break
    print(f"Match at {idx}:", data[idx:idx+80])
    idx += len(target)

target_http = 'http://'.encode('utf-16le')
idx = 0
while True:
    idx = data.find(target_http, idx)
    if idx == -1:
        break
    print(f"HTTP Match at {idx}:", data[idx:idx+80])
    idx += len(target_http)
