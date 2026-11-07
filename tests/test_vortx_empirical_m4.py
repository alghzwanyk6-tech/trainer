"""
test_vortx_empirical_m4.py - Empirical Challenger 2 Test Suite for Milestone M4
Validates Machine Learning, Computer Vision, and Streaming claims in TECHNICAL_ANALYSIS_REPORT.md
"""

import os
import sys
import json
import struct
import re
import pytest

ROOT_DIR = r"c:\Users\96655\Downloads\__VORTX STORE_ نسخة"

def find_vortx_buy():
    for root, dirs, files in os.walk(ROOT_DIR):
        if os.path.basename(root) == "Vortx_buy":
            return root
    raise FileNotFoundError("Vortx_buy directory not found")

VORTX_BUY = find_vortx_buy()

def get_pe_machine(filepath):
    with open(filepath, "rb") as f:
        dos_header = f.read(64)
        if dos_header[:2] != b"MZ":
            return "NOT_PE"
        pe_offset = struct.unpack("<I", dos_header[60:64])[0]
        f.seek(pe_offset)
        pe_sig = f.read(4)
        if pe_sig != b"PE\x00\x00":
            return "INVALID_PE"
        machine = struct.unpack("<H", f.read(2))[0]
        if machine == 0x8664:
            return "x64"
        elif machine == 0x014c:
            return "x86"
        elif machine == 0xaa64:
            return "ARM64"
        return f"0x{machine:04x}"


# ============================================================================
# 1. Model Files & Magic Header (LCM1)
# ============================================================================
class TestModelFiles:
    EXPECTED_MODELS = {
        "Lucifer-Head-only.onnx.enc": 10604564,
        "LuciferBestV2-5.onnx.enc": 10569988,
        "LuciferBestV2.onnx.enc": 10569988,
        "LuciferStrongestV3.onnx.enc": 10457380,
    }

    def test_model_directory_and_counts(self):
        models_dir = os.path.join(VORTX_BUY, "models")
        assert os.path.isdir(models_dir), f"Models dir {models_dir} does not exist"
        files = sorted(os.listdir(models_dir))
        assert files == sorted(list(self.EXPECTED_MODELS.keys())), f"Unexpected files in models dir: {files}"

    @pytest.mark.parametrize("model_name,expected_size", EXPECTED_MODELS.items())
    def test_model_exact_size_and_lcm1_header(self, model_name, expected_size):
        path = os.path.join(VORTX_BUY, "models", model_name)
        actual_size = os.path.getsize(path)
        assert actual_size == expected_size, f"{model_name}: expected {expected_size} bytes, got {actual_size}"

        with open(path, "rb") as f:
            header = f.read(4)
        assert header == b"LCM1", f"{model_name}: expected b'LCM1' header, got {header!r}"
        assert header.hex() == "4c434d31", f"{model_name}: expected hex 4c434d31, got {header.hex()}"


# ============================================================================
# 2. DirectML, OpenCV, and ONNX Runtime Libraries
# ============================================================================
class TestMLAndVisionBinaries:
    def test_directml_binary(self):
        dml_path = os.path.join(VORTX_BUY, "DirectML.dll")
        assert os.path.isfile(dml_path), "DirectML.dll missing in Vortx_buy"
        size = os.path.getsize(dml_path)
        assert size == 27383832, f"DirectML.dll size mismatch: {size}"
        assert get_pe_machine(dml_path) == "x64"

    def test_onnxruntime_binary(self):
        ort_path = os.path.join(VORTX_BUY, "onnxruntime.dll")
        assert os.path.isfile(ort_path), "onnxruntime.dll missing in Vortx_buy"
        size = os.path.getsize(ort_path)
        assert size == 13804000, f"onnxruntime.dll size mismatch: {size}"
        assert get_pe_machine(ort_path) == "x64"

    def test_opencv_binaries(self):
        opencv_root = os.path.join(VORTX_BUY, "OpenCvSharpExtern.dll")
        opencv_x64 = os.path.join(VORTX_BUY, "dll", "x64", "OpenCvSharpExtern.dll")
        opencv_x86 = os.path.join(VORTX_BUY, "dll", "x86", "OpenCvSharpExtern.dll")

        assert os.path.isfile(opencv_root), "OpenCvSharpExtern.dll missing in root"
        assert os.path.isfile(opencv_x64), "OpenCvSharpExtern.dll missing in dll/x64"
        assert os.path.isfile(opencv_x86), "OpenCvSharpExtern.dll missing in dll/x86"

        assert os.path.getsize(opencv_root) == 62044672
        assert os.path.getsize(opencv_x64) == 62044672
        assert os.path.getsize(opencv_x86) == 42627072

        assert get_pe_machine(opencv_root) == "x64"
        assert get_pe_machine(opencv_x64) == "x64"
        assert get_pe_machine(opencv_x86) == "x86"

    def test_vortx_stream_directml_references(self):
        stream_path = os.path.join(VORTX_BUY, "rm_re_fr", "Vortx Stream.exe")
        assert os.path.isfile(stream_path)
        assert get_pe_machine(stream_path) == "x64"

        with open(stream_path, "rb") as f:
            data = f.read()

        # Check IL / metadata references
        assert b"AppendExecutionProvider_DML" in data
        assert b"OpenCvSharp" in data
        assert b"Cv2" in data
        assert b"YoloDetector" in data
        assert b"TrackedObject" in data
        assert b"FlashCap" in data
        assert b"DXGI" in data


# ============================================================================
# 3. Electron app.asar Xbox Streaming Subsystem
# ============================================================================
class TestElectronAppAsar:
    @classmethod
    def setup_class(cls):
        cls.asar_path = os.path.join(VORTX_BUY, "xlu", "resources", "app.asar")
        assert os.path.isfile(cls.asar_path)

        with open(cls.asar_path, "rb") as f:
            header_raw = f.read(16)
            magic, total_size, size2, json_len = struct.unpack("<IIII", header_raw)
            cls.header = json.loads(f.read(json_len).decode("utf-8"))
            cls.data_offset = (16 + json_len + 3) & ~3

    def read_asar_file(self, path_parts):
        curr = self.header
        for p in path_parts:
            curr = curr["files"][p]
        offset = self.data_offset + int(curr["offset"])
        size = int(curr["size"])
        with open(self.asar_path, "rb") as f:
            f.seek(offset)
            return f.read(size)

    def test_package_json_metadata(self):
        pkg_bytes = self.read_asar_file(["package.json"])
        pkg = json.loads(pkg_bytes.decode("utf-8"))

        assert pkg["name"] == "greenlight-desktop"
        assert pkg["productName"] == "Lucifer"
        assert pkg["version"] == "2.4.2"
        assert pkg["main"] == "app/background.js"

        deps = pkg["dependencies"]
        assert "axios" in deps
        assert "express" in deps
        assert "koffi" in deps
        assert "xal-node" in deps
        assert "xbox-webapi" in deps
        assert "xbox-xcloud-player" in deps

    def test_background_js_routes_and_ports(self):
        bg_bytes = self.read_asar_file(["app", "background.js"])
        bg_text = bg_bytes.decode("utf-8", errors="ignore")

        # Verify express routes
        assert "/api/stream/status" in bg_text
        assert "/api/:channel/:action" in bg_text

        # Verify port 5218 in string/code
        assert "5218" in bg_text


# ============================================================================
# 4. PlayStation Remote Play Subsystem (lu.exe / Chiaki)
# ============================================================================
class TestPlayStationStreaming:
    def test_lu_binary_and_symbols(self):
        lu_path = os.path.join(VORTX_BUY, "rm_re_fr", "lu.exe")
        assert os.path.isfile(lu_path)
        assert get_pe_machine(lu_path) == "x64"
        assert os.path.getsize(lu_path) == 6139904

        with open(lu_path, "rb") as f:
            data = f.read()

        assert b"Chiaki" in data or b"Chiaki" in data.decode("latin1", errors="ignore").encode("ascii", errors="ignore")
        assert b"9003" in data

    def test_qt6_and_multimedia_dlls(self):
        rm_re_fr = os.path.join(VORTX_BUY, "rm_re_fr")
        required_dlls = [
            "Qt6Core.dll",
            "Qt6Gui.dll",
            "Qt6Widgets.dll",
            "Qt6Network.dll",
            "Qt6Quick.dll",
            "SDL3.dll",
            "avcodec-61.dll",
            "avutil-59.dll",
            "swscale-8.dll",
            "vulkan-1.dll",
        ]
        for dll in required_dlls:
            dll_path = os.path.join(rm_re_fr, dll)
            assert os.path.isfile(dll_path), f"Missing {dll} in rm_re_fr"
            assert get_pe_machine(dll_path) == "x64", f"{dll} is not x64"


# ============================================================================
# 5. Kinematic Engine, Presets, and Verifier Model
# ============================================================================
class TestKinematicEngineAndPresets:
    @classmethod
    def setup_class(cls):
        stream_path = os.path.join(VORTX_BUY, "rm_re_fr", "Vortx Stream.exe")
        with open(stream_path, "rb") as f:
            cls.stream_data = f.read()

    def test_verifier_onnx_presence(self):
        # In .NET CLR assemblies, user strings in the #US heap are stored in UTF-16LE
        assert "verifier.onnx".encode("utf-16le") in self.stream_data
        assert "CAcSB3B5dG9yY2gaBjIuMTEuMD".encode("utf-16le") in self.stream_data

    def test_tracked_object_kinematic_fields(self):
        expected_fields = [
            "VelX", "VelY", "MotionEma", "StillFrames", "IsStaticProp",
            "GetPredictedRect", "IsTeammate", "IsHead", "MissedFrames",
            "RawCX", "RawCY"
        ]
        for field in expected_fields:
            assert field.encode("ascii") in self.stream_data, f"Field {field} not found in metadata"

    def test_targeting_presets_presence(self):
        presets = [
            "SUNXDS 0.8", "sunxds",
            "AIO HEADS", "AIOHeads",
            "WARZONE 50k", "WZ_50k",
            "BO6 PURPLE", "BO6_PURPLE",
            "BO7 NAMETAGS", "NameTags",
            "ENFORCER", "Enforcer",
            "RIVALS", "Rivals",
            "yolo11m",
        ]
        for p in presets:
            found = (p.encode("utf-16le") in self.stream_data) or (p.encode("ascii") in self.stream_data)
            assert found, f"Preset {p} not found in binary strings"


# ============================================================================
# 6. Licensing, Cloud Endpoints & Discrepancies
# ============================================================================
class TestCloudEndpointsAndDiscrepancies:
    @classmethod
    def setup_class(cls):
        stream_path = os.path.join(VORTX_BUY, "rm_re_fr", "Vortx Stream.exe")
        with open(stream_path, "rb") as f:
            cls.stream_data = f.read()

    def test_licensing_and_auth_endpoints(self):
        endpoints = [
            "urscript.shop",
            "luciferstore.store",
            "lucifer-scriptss",
            "/api/c/activate",
            "/api/c/heartbeat",
            "/api/c/verify",
            "psntools.com",
            "flipscreen.games",
            "microsoft.com/link",
        ]
        for ep in endpoints:
            assert ep.encode("utf-16le") in self.stream_data, f"Endpoint {ep} missing in strings"

    def test_directml_and_ort_location_fact_check(self):
        # Section 2.4 ASCII tree shows onnxruntime.dll and DirectML.dll under rm_re_fr/
        # Empirically verify that they actually reside in Vortx_buy root directory:
        root_dml = os.path.join(VORTX_BUY, "DirectML.dll")
        root_ort = os.path.join(VORTX_BUY, "onnxruntime.dll")
        assert os.path.isfile(root_dml)
        assert os.path.isfile(root_ort)

        rm_re_fr_dml = os.path.join(VORTX_BUY, "rm_re_fr", "DirectML.dll")
        rm_re_fr_ort = os.path.join(VORTX_BUY, "rm_re_fr", "onnxruntime.dll")
        # Note the structural difference: they are NOT in rm_re_fr on disk
        assert not os.path.exists(rm_re_fr_dml)
        assert not os.path.exists(rm_re_fr_ort)

    def test_libplacebo_version_fact_check(self):
        # Section 5.2 claims placebo-349.dll
        # On disk, verify that the actual library is libplacebo-365.dll
        rm_re_fr = os.path.join(VORTX_BUY, "rm_re_fr")
        assert os.path.isfile(os.path.join(rm_re_fr, "libplacebo-365.dll"))
        assert not os.path.exists(os.path.join(rm_re_fr, "placebo-349.dll"))
