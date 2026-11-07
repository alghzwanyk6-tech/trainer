import time
try:
    import vgamepad as vg
    print("[+] vgamepad imported successfully.")
    
    pad = vg.VDS4Gamepad()
    print("[+] Virtual DualShock 4 created.")
    
    # تحريك خفيف للتجربة
    pad.right_joystick_float(x_value_float=0.5, y_value_float=0.0)
    pad.update()
    time.sleep(0.5)
    
    # تصفير العصا
    pad.right_joystick_float(x_value_float=0.0, y_value_float=0.0)
    pad.update()
    print("[+] Joystick reset successfully. System is ready.")

except Exception as e:
    print(f"[-] Error: {e}")