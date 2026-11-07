import subprocess
import json
import winreg

print("=== Checking Gaming Devices via WinMM ===")
import ctypes
winmm = ctypes.windll.winmm
num_devs = winmm.joyGetNumDevs()
print(f"joyGetNumDevs: {num_devs}")

class JOYINFOEX(ctypes.Structure):
    _fields_ = [
        ("dwSize", ctypes.c_uint),
        ("dwFlags", ctypes.c_uint),
        ("dwXpos", ctypes.c_uint),
        ("dwYpos", ctypes.c_uint),
        ("dwZpos", ctypes.c_uint),
        ("dwRpos", ctypes.c_uint),
        ("dwUpos", ctypes.c_uint),
        ("dwVpos", ctypes.c_uint),
        ("dwButtons", ctypes.c_uint),
        ("dwButtonNumber", ctypes.c_uint),
        ("dwPOV", ctypes.c_uint),
        ("dwReserved1", ctypes.c_uint),
        ("dwReserved2", ctypes.c_uint),
    ]

for i in range(min(num_devs, 16)):
    ji = JOYINFOEX()
    ji.dwSize = ctypes.sizeof(JOYINFOEX)
    ji.dwFlags = 0xFF # JOY_RETURNALL
    res = winmm.joyGetPosEx(i, ctypes.byref(ji))
    if res == 0:
        print(f"WinMM Joystick {i} CONNECTED! Buttons: {ji.dwButtons}")

print("=== Checking XInput ===")
for dll_name in ['xinput1_4.dll', 'xinput1_3.dll', 'xinput9_1_0.dll']:
    try:
        xi = ctypes.windll.LoadLibrary(dll_name)
        for i in range(4):
            class XINPUT_STATE(ctypes.Structure):
                _fields_ = [("dwPacketNumber", ctypes.c_uint), ("Gamepad", ctypes.c_byte * 12)]
            xs = XINPUT_STATE()
            if xi.XInputGetState(i, ctypes.byref(xs)) == 0:
                print(f"XInput ({dll_name}) device {i} CONNECTED!")
    except Exception as e:
        pass

print("=== Checking Pygame Joystick ===")
try:
    import pygame
    pygame.init()
    pygame.joystick.init()
    cnt = pygame.joystick.get_count()
    print(f"Pygame joystick count: {cnt}")
    for i in range(cnt):
        js = pygame.joystick.Joystick(i)
        js.init()
        print(f"  [{i}] {js.get_name()}")
except Exception as e:
    print(f"Pygame error: {e}")

print("=== Checking Active Windows ===")
user32 = ctypes.windll.user32
def enum_cb(hwnd, _):
    if user32.IsWindowVisible(hwnd):
        buf = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(hwnd, buf, 512)
        title = buf.value.strip()
        if title:
            for k in ['chiaki', 'remote', 'playstation', 'call of duty', 'aim']:
                if k in title.lower():
                    print(f"Found Window: HWND {hwnd} | '{title}'")
    return True

WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
