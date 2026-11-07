import os
import pygame

for driver in ["windows", "directinput", "rawinput", "hidapi"]:
    os.environ["SDL_JOYSTICK_DRIVER"] = driver
    try:
        pygame.quit()
        pygame.init()
        pygame.joystick.init()
        cnt = pygame.joystick.get_count()
        print(f"Driver '{driver}': count = {cnt}")
        for i in range(cnt):
            js = pygame.joystick.Joystick(i)
            js.init()
            print(f"   Device {i}: {js.get_name()}")
    except Exception as e:
        print(f"Driver '{driver}' error: {e}")
