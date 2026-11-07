import os
import struct
import subprocess

def get_vortx_buy_dir():
    root = r"c:\Users\96655\Downloads\__VORTX STORE_ نسخة"
    for r, dirs, files in os.walk(root):
        if os.path.basename(r) == "Vortx_buy":
            return r
    raise FileNotFoundError("Could not find Vortx_buy directory")

vortx_buy = get_vortx_buy_dir()

# 1. Investigate directory count
print("--- Investigating Directory Count ---")
# Count directories starting from root vs Vortx_buy
all_dirs_under_root = []
root = r"c:\Users\96655\Downloads\__VORTX STORE_ نسخة"
for r, dirs, files in os.walk(root):
    for d in dirs:
        all_dirs_under_root.append(os.path.join(r, d))

dirs_under_vortx_buy = []
for r, dirs, files in os.walk(vortx_buy):
    for d in dirs:
        dirs_under_vortx_buy.append(os.path.join(r, d))

print(f"Total dirs under root '{root}': {len(all_dirs_under_root)}")
print(f"Total dirs under Vortx_buy: {len(dirs_under_vortx_buy)}")
# 214 under Vortx_buy + 4 parents = 218!
# Parent 1: __VORTX STORE_ نسخة (root)
# Parent 2: \u200f\u200fVORTX STORE_ نسخة
# Parent 3: Vortx (1)
# Parent 4: Vortx
# Then Vortx_buy has 214 subdirs! Total = 214 + 4 = 218!

# 2. Investigate HidHide_1.5.230_x64.exe machine architecture
print("\n--- Investigating HidHide_1.5.230_x64.exe Architecture ---")
hh_path = os.path.join(vortx_buy, r"Very important to install\HidHide_1.5.230_x64.exe")
with open(hh_path, "rb") as f:
    data = f.read(1024)
pe_off = struct.unpack_from("<I", data, 0x3C)[0]
with open(hh_path, "rb") as f:
    f.seek(pe_off)
    pe_hdr = f.read(32)
sig = pe_hdr[:4]
machine = struct.unpack_from("<H", pe_hdr, 4)[0]
print(f"HidHide signature: {sig}, machine: 0x{machine:04x}")

# 3. Investigate all 208 binaries (.exe, .dll, .node)
print("\n--- Investigating 208 Binaries ---")
binaries = []
for r, dirs, files in os.walk(vortx_buy):
    for f in files:
        ext = os.path.splitext(f)[1].lower()
        if ext in [".exe", ".dll", ".node"]:
            binaries.append(os.path.join(r, f))

print(f"Total files with .exe, .dll, .node: {len(binaries)}")

non_pe = []
machine_map = {}
for b in binaries:
    with open(b, "rb") as f:
        head = f.read(64)
    if head[:2] != b"MZ":
        non_pe.append((b, "Not MZ"))
        continue
    pe_off = struct.unpack_from("<I", head, 0x3C)[0]
    with open(b, "rb") as f:
        f.seek(pe_off)
        sig = f.read(4)
        if sig != b"PE\x00\x00":
            non_pe.append((b, f"Bad PE sig: {sig}"))
            continue
        m = struct.unpack("<H", f.read(2))[0]
        m_hex = f"0x{m:04x}"
        machine_map[m_hex] = machine_map.get(m_hex, 0) + 1
        if m == 0x014c and "HidHide" in b:
            print(f"CONFIRMED: HidHide is indeed 0x014c (i386)!")

print(f"Machine architectures breakdown across all {len(binaries)} files:")
for m_hex, c in sorted(machine_map.items()):
    print(f"  {m_hex}: {c}")
print(f"Non-PE files among binaries: {len(non_pe)}")
for np in non_pe:
    print(f"  {np}")
