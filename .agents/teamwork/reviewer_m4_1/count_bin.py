import os

root = r'c:\Users\96655\Downloads\__VORTX STORE_ نسخة'
vortx_buy = None
for r, d, f in os.walk(root):
    if os.path.basename(r) == 'Vortx_buy':
        vortx_buy = r
        break

binaries = []
for r, d, f in os.walk(vortx_buy):
    for file in f:
        ext = os.path.splitext(file)[1].lower()
        if ext in ('.dll', '.exe', '.node'):
            binaries.append(os.path.join(r, file))

print(f"Total .dll, .exe, .node files: {len(binaries)}")
