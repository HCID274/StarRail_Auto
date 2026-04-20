"""最小化鼠标移动测试 — 诊断 pyautogui 是否能控制鼠标."""

import time
import ctypes

# 1. 检查 DPI awareness
try:
    awareness = ctypes.c_int()
    ctypes.windll.shcore.GetProcessDpiAwareness(0, ctypes.byref(awareness))
    print(f"[DPI] current awareness: {awareness.value} (0=unaware, 1=system, 2=per-monitor)")
except Exception as e:
    print(f"[DPI] check failed: {e}")

# 2. 设置 DPI awareness 为 per-monitor（解决 125% 缩放坐标偏移）
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
    print("[DPI] set to per-monitor aware (2)")
except Exception as e:
    print(f"[DPI] set failed (may already be set): {e}")

import pyautogui

# 3. 基础信息
print(f"[INFO] screen size: {pyautogui.size()}")
print(f"[INFO] current mouse pos: {pyautogui.position()}")

# 4. 测试移动
targets = [(500, 500), (1000, 500), (500, 800)]
for x, y in targets:
    print(f"[MOVE] moving to ({x}, {y})...")
    pyautogui.moveTo(x, y, duration=0.5)
    actual = pyautogui.position()
    print(f"[MOVE] actual position: {actual}")
    time.sleep(1)

print("[DONE] test finished")
