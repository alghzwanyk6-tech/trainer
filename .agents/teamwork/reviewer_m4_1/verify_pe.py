import os, struct
from collections import defaultdict

root = r'c:\Users\96655\Downloads\__VORTX STORE_ نسخة'
vortx_buy = None
for r, d, f in os.walk(root):
    if os.path.basename(r) == 'Vortx_buy':
        vortx_buy = r
        break

def get_pe_machine(filepath):
    try:
        with open(filepath, 'rb') as f:
            dos_header = f.read(64)
            if len(dos_header) < 64 or dos_header[:2] != b'MZ':
                return None
            e_lfanew = struct.unpack('<I', dos_header[60:64])[0]
            f.seek(e_lfanew)
            pe_sig = f.read(4)
            if pe_sig != b'PE\x00\x00':
                return None
            coff_header = f.read(20)
            if len(coff_header) < 20:
                return None
            machine = struct.unpack('<H', coff_header[:2])[0]
            return machine
    except:
        return None

machine_names = {
    0x8664: 'x64 (AMD64)',
    0x014c: 'x86 (i386)',
    0xaa64: 'ARM64',
    0x0200: 'IA64'
}

pe_files = []
machine_counts = defaultdict(int)

for r, d, f in os.walk(vortx_buy):
    for file in f:
        fp = os.path.join(r, file)
        m = get_pe_machine(fp)
        if m is not None:
            pe_files.append((fp, m))
            machine_counts[m] += 1

print(f"Total PE files found: {len(pe_files)}")
for m, cnt in machine_counts.items():
    name = machine_names.get(m, hex(m))
    pct = (cnt / len(pe_files)) * 100
    print(f"  {name:15}: {cnt} ({pct:.1f}%)")
