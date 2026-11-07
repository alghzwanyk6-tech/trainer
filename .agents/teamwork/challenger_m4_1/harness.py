import os
import sys
import hashlib
import zipfile
import subprocess
import struct
import json

def get_vortx_buy_dir():
    root = r"c:\Users\96655\Downloads\__VORTX STORE_ نسخة"
    for r, dirs, files in os.walk(root):
        if os.path.basename(r) == "Vortx_buy":
            return r
    raise FileNotFoundError("Could not find Vortx_buy directory")

def test_directory_and_files(vortx_buy):
    print("\n=== TEST 2: Inventory Counts & Extensions in Vortx_buy ===")
    total_files = 0
    total_dirs = 0
    total_bytes = 0
    files_excl_report = 0
    bytes_excl_report = 0
    ext_counts = {}
    ext_sizes = {}

    for r, dirs, files in os.walk(vortx_buy):
        total_dirs += len(dirs)
        for f in files:
            total_files += 1
            fp = os.path.join(r, f)
            sz = os.path.getsize(fp)
            total_bytes += sz

            if f != "TECHNICAL_ANALYSIS_REPORT.md":
                files_excl_report += 1
                bytes_excl_report += sz
                _, ext = os.path.splitext(f)
                ext = ext.lower() if ext else "(no extension)"
                ext_counts[ext] = ext_counts.get(ext, 0) + 1
                ext_sizes[ext] = ext_sizes.get(ext, 0) + sz

    print(f"Total files on disk: {total_files}")
    print(f"Total files excluding deliverable report: {files_excl_report}")
    print(f"Total dirs: {total_dirs}")
    print(f"Total bytes on disk: {total_bytes} ({total_bytes / (1024*1024):.2f} MB)")
    print(f"Total bytes excluding deliverable report: {bytes_excl_report} ({bytes_excl_report / (1024*1024):.2f} MB)")

    print("\nFile extension breakdown (excluding report):")
    sorted_exts = sorted(ext_counts.items(), key=lambda x: x[1], reverse=True)
    for ext, count in sorted_exts[:20]:
        sz = ext_sizes[ext]
        print(f"  {ext:16s}: count={count:4d}, size={sz:12d} bytes ({sz/(1024*1024):6.2f} MB)")

    # Compare with claims:
    # 2,590 files, 218 directories, 1,283,193,737 bytes
    match_files = (files_excl_report == 2590)
    match_dirs = (total_dirs == 218)
    match_bytes = (bytes_excl_report == 1283193737)
    print(f"\nAssertion Check vs Report Claims:")
    print(f"  Files == 2590: {match_files} (actual excl report: {files_excl_report}, with report: {total_files})")
    print(f"  Dirs == 218: {match_dirs} (actual: {total_dirs})")
    print(f"  Bytes == 1283193737: {match_bytes} (actual excl report: {bytes_excl_report}, diff: {bytes_excl_report - 1283193737})")
    return match_files and match_dirs and match_bytes

def test_models(vortx_buy):
    print("\n=== TEST 3: Encrypted Model Verification ===")
    models_dir = os.path.join(vortx_buy, "models")
    expected = {
        "Lucifer-Head-only.onnx.enc": 10604564,
        "LuciferBestV2-5.onnx.enc": 10569988,
        "LuciferBestV2.onnx.enc": 10569988,
        "LuciferStrongestV3.onnx.enc": 10457380
    }
    all_ok = True
    for name, exp_sz in expected.items():
        fp = os.path.join(models_dir, name)
        if not os.path.exists(fp):
            print(f"MISSING: {name}")
            all_ok = False
            continue
        sz = os.path.getsize(fp)
        with open(fp, "rb") as f:
            header = f.read(4)
        magic = header.decode("latin1", errors="replace")
        ok = (sz == exp_sz) and (magic == "LCM1")
        print(f"Model: {name} -> size={sz} (exp {exp_sz}), magic={magic} (exp 'LCM1') -> {'PASS' if ok else 'FAIL'}")
        if not ok:
            all_ok = False
    return all_ok

def parse_pe(fp):
    try:
        with open(fp, "rb") as f:
            data = f.read(1024)
        if len(data) < 64 or data[:2] != b"MZ":
            return None
        pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
        with open(fp, "rb") as f:
            f.seek(pe_offset)
            pe_hdr = f.read(256)
        if len(pe_hdr) < 24 or pe_hdr[:4] != b"PE\x00\x00":
            return None
        machine = struct.unpack_from("<H", pe_hdr, 4)[0]
        opt_hdr_magic = struct.unpack_from("<H", pe_hdr, 24)[0]
        is_pe32_plus = (opt_hdr_magic == 0x20b)
        
        # Read DataDirectory[14] (CLR runtime header)
        # For PE32 (0x10b): optional header standard fields (28 bytes) + NT fields (68 bytes) + 14 * 8 = offset 24 + 96 + 112 = 232
        # For PE32+ (0x20b): optional header standard fields (24 bytes) + NT fields (88 bytes) + 14 * 8 = offset 24 + 112 + 112 = 248
        clr_va = 0
        with open(fp, "rb") as f:
            if is_pe32_plus:
                f.seek(pe_offset + 24 + 112 + 14 * 8)
            else:
                f.seek(pe_offset + 24 + 96 + 14 * 8)
            dd_bytes = f.read(8)
            if len(dd_bytes) == 8:
                clr_va, clr_sz = struct.unpack_from("<II", dd_bytes, 0)
        return {
            "machine": machine,
            "machine_hex": f"0x{machine:04x}",
            "is_clr": clr_va > 0
        }
    except Exception as e:
        return None

def test_pe_binaries(vortx_buy):
    print("\n=== TEST 4: PE Binary Architecture Survey ===")
    counts = {"0x8664": 0, "0x014c": 0, "0xaa64": 0, "other": 0}
    clr_count = 0
    total_pe = 0
    pe_list = []

    for r, dirs, files in os.walk(vortx_buy):
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in [".exe", ".dll", ".node"]:
                fp = os.path.join(r, f)
                info = parse_pe(fp)
                if info:
                    total_pe += 1
                    m_hex = info["machine_hex"]
                    if m_hex in counts:
                        counts[m_hex] += 1
                    else:
                        counts["other"] += 1
                    if info["is_clr"]:
                        clr_count += 1
                    pe_list.append((fp, info))

    print(f"Total PE binaries identified: {total_pe}")
    print(f"  x64 AMD64 (0x8664): {counts['0x8664']}")
    print(f"  x86 i386 (0x014c): {counts['0x014c']}")
    print(f"  ARM64 (0xaa64): {counts['0xaa64']}")
    print(f"  Managed CLR assemblies: {clr_count}")

    # Check Table 3.2 binaries
    print("\nTable 3.2 Binaries Check:")
    t32_binaries = [
        (os.path.join(vortx_buy, r"rm_re_fr\Vortx Stream.exe"), 7665152, "0x8664"),
        (os.path.join(vortx_buy, r"rm_re_fr\lu.exe"), 6139904, "0x8664"),
        (os.path.join(vortx_buy, r"xlu\xlu.exe"), 227062784, "0x8664"),
        (os.path.join(vortx_buy, r"Very important to install\NDP48-x86-x64-AllOS-ENU.exe"), 121346568, "0x014c"),
        (os.path.join(vortx_buy, r"Very important to install\ViGEmBus_1.22.0_x64_x86_arm64.exe"), 6278576, "0x014c"),
        (os.path.join(vortx_buy, r"Very important to install\HidHide_1.5.230_x64.exe"), 8078016, "0x8664"),
        (os.path.join(vortx_buy, r"xlu\resources\elevate.exe"), 107520, "0x014c")
    ]
    t32_ok = True
    for fp, exp_sz, exp_arch in t32_binaries:
        if not os.path.exists(fp):
            print(f"MISSING: {fp}")
            t32_ok = False
            continue
        sz = os.path.getsize(fp)
        pe_info = parse_pe(fp)
        arch = pe_info["machine_hex"] if pe_info else "UNKNOWN"
        ok = (sz == exp_sz) and (arch == exp_arch)
        print(f"  {os.path.basename(fp):35s} size={sz:9d} (exp {exp_sz}), arch={arch} (exp {exp_arch}) -> {'PASS' if ok else 'FAIL'}")
        if not ok:
            t32_ok = False

    claims_match = (
        total_pe == 208 and
        counts["0x8664"] == 160 and
        counts["0x014c"] == 32 and
        counts["0xaa64"] == 1 and
        clr_count == 21 and
        t32_ok
    )
    print(f"\nPE Architecture Claims Match: {claims_match}")
    return claims_match

def test_missing_binary_and_quarantine():
    print("\n=== TEST 5: Quarantined Binary & Zip Verification ===")
    zip_path = r"c:\Users\96655\Downloads\__VORTX STORE_ نسخة.zip"
    if not os.path.exists(zip_path):
        print(f"FAIL: zip not found: {zip_path}")
        return False
    
    with zipfile.ZipFile(zip_path, "r") as z:
        found_entry = None
        for info in z.infolist():
            if info.filename.endswith("Vortx.exe"):
                found_entry = info
                break
        
        if not found_entry:
            print("FAIL: Vortx.exe not found in zip archive")
            return False
        
        print(f"Found zip entry: {found_entry.filename}")
        print(f"  Uncompressed size: {found_entry.file_size} (exp 6599168)")
        data = z.read(found_entry)
        h = hashlib.sha256(data).hexdigest()
        print(f"  SHA-256: {h}")
        exp_h = "8f7d530905ed63c128921d080542459aa492fec43fba3c6ce4e694712ea118cb"
        zip_ok = (found_entry.file_size == 6599168) and (h.lower() == exp_h.lower())
        print(f"  Zip entry check -> {'PASS' if zip_ok else 'FAIL'}")

    # Companion build check
    comp_exe = r"c:\Users\96655\Downloads\Color_detection\Color Detection_Secure\Color Detection.exe"
    comp_pdb = r"c:\Users\96655\Downloads\Color_detection\Color Detection_Secure\Color Detection.pdb"
    exe_exists = os.path.exists(comp_exe)
    pdb_exists = os.path.exists(comp_pdb)
    pdb_sz = os.path.getsize(comp_pdb) if pdb_exists else 0
    print(f"Companion Color Detection.exe exists: {exe_exists}")
    print(f"Companion Color Detection.pdb exists: {pdb_exists}, size={pdb_sz} (exp 572928)")
    comp_ok = exe_exists and pdb_exists and (pdb_sz == 572928)

    # Defender threat log check via PowerShell
    print("\nChecking Defender Threat Logs via PowerShell...")
    ps_cmd = 'Get-MpThreatDetection | Where-Object { $_.Resources -match "Vortx.exe" } | Select-Object ThreatName, SeverityID, InitialDetectionTime, Resources | ConvertTo-Json'
    res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True)
    def_ok = False
    if res.returncode == 0 and res.stdout.strip():
        try:
            threat_data = json.loads(res.stdout)
            if isinstance(threat_data, list):
                threat_data = threat_data[0]
            print(f"Defender ThreatName: {threat_data.get('ThreatName')}")
            print(f"Defender SeverityID: {threat_data.get('SeverityID')}")
            print(f"Defender Resources: {threat_data.get('Resources')}")
            if "Wacatac" in threat_data.get("ThreatName", "") and "Vortx.exe" in threat_data.get("Resources", ""):
                def_ok = True
        except Exception as e:
            print(f"Error parsing Defender JSON: {e}, raw stdout: {res.stdout}")
    else:
        print(f"Defender query returned code {res.returncode}, stdout: {res.stdout}, stderr: {res.stderr}")

    return zip_ok and comp_ok and def_ok

if __name__ == "__main__":
    vortx_buy = get_vortx_buy_dir()
    print(f"Resolved Vortx_buy directory: {vortx_buy}")
    t2 = test_directory_and_files(vortx_buy)
    t3 = test_models(vortx_buy)
    t4 = test_pe_binaries(vortx_buy)
    t5 = test_missing_binary_and_quarantine()
    print(f"\nOVERALL SUMMARY:")
    print(f"Test 2 (Inventory & Extensions): {'PASS' if t2 else 'FAIL'}")
    print(f"Test 3 (Encrypted Models): {'PASS' if t3 else 'FAIL'}")
    print(f"Test 4 (PE Binary Architectures): {'PASS' if t4 else 'FAIL'}")
    print(f"Test 5 (Missing Binary & Defender): {'PASS' if t5 else 'FAIL'}")
