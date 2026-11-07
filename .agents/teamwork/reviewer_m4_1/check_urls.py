import re

asar_path = r'c:\Users\96655\Downloads\__VORTX STORE_ نسخة\‏‏VORTX STORE_ نسخة\Vortx (1)\Vortx\Vortx_buy\xlu\resources\app.asar'
with open(asar_path, 'rb') as f:
    data = f.read()

matches = re.findall(rb'https?://[^\s"\'<>]+', data)
for m in sorted(set(matches)):
    m_lower = m.lower()
    if b'microsoft' in m_lower or b'xbox' in m_lower:
        print(m.decode('utf-8', errors='ignore'))
