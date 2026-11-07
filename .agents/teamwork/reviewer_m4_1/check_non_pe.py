import os

root = r'c:\Users\96655\Downloads\__VORTX STORE_ نسخة'
vortx_buy = None
for r, d, f in os.walk(root):
    if os.path.basename(r) == 'Vortx_buy':
        vortx_buy = r
        break

for r, d, f in os.walk(vortx_buy):
    for file in f:
        ext = os.path.splitext(file)[1].lower()
        if ext in ('.dll', '.exe', '.node'):
            fp = os.path.join(r, file)
            with open(fp, 'rb') as fp_in:
                head = fp_in.read(4)
                if head[:2] != b'MZ':
                    print(f"Non-PE binary: {file} header: {head}")
