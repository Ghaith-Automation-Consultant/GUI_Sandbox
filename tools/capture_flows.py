# Copyright 2026 Ghaith Abdessalem
# SPDX-License-Identifier: Apache-2.0
"""Walk the sandbox's transaction flows and save a screenshot of each step."""
import ctypes
import sys
from pathlib import Path

import win32gui
import win32ui
from PIL import Image
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from main import MainWindow  # noqa: E402
from ui.styles import sap_global_stylesheet  # noqa: E402

OUT_DIR = ROOT / "screens" / "screenshots"


def find_window():
    result = []

    def cb(hwnd, _):
        if win32gui.IsWindowVisible(hwnd) and "GUI Sandbox" in win32gui.GetWindowText(hwnd):
            result.append(hwnd)

    win32gui.EnumWindows(cb, None)
    return result[0] if result else None


def take_screenshot(name):
    hwnd = find_window()
    if not hwnd:
        print(f"  {name}: window not found")
        return
    rect = win32gui.GetWindowRect(hwnd)
    w, h = rect[2] - rect[0], rect[3] - rect[1]
    hwnd_dc = win32gui.GetWindowDC(hwnd)
    mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
    save_dc = mfc_dc.CreateCompatibleDC()
    bmp = win32ui.CreateBitmap()
    bmp.CreateCompatibleBitmap(mfc_dc, w, h)
    save_dc.SelectObject(bmp)
    ctypes.windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), 2)
    info = bmp.GetInfo()
    img = Image.frombuffer(
        "RGB", (info["bmWidth"], info["bmHeight"]), bmp.GetBitmapBits(True), "raw", "BGRX", 0, 1
    )
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    img.save(OUT_DIR / f"flow_{name}.png")
    print(f"  {name}: saved ({w}x{h})")
    save_dc.DeleteDC()
    mfc_dc.DeleteDC()
    win32gui.ReleaseDC(hwnd, hwnd_dc)


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(sap_global_stylesheet())

    win = MainWindow()
    win.show()

    steps = [
        (300, lambda: print("=== SE16 Flow ===")),
        (100, lambda: win.router.navigate("SE16")),
        (500, lambda: take_screenshot("SE16_1_initial")),
        (100, lambda: win.router.next_step()),
        (500, lambda: take_screenshot("SE16_2_selection")),
        (100, lambda: win.router.next_step()),
        (500, lambda: take_screenshot("SE16_3_results")),
        (300, lambda: print("=== SE38 Flow ===")),
        (100, lambda: win.router.navigate("SE38")),
        (500, lambda: take_screenshot("SE38_1_initial")),
        (100, lambda: win.router.next_step()),
        (500, lambda: take_screenshot("SE38_2_source")),
        (100, lambda: win.router.next_step()),
        (500, lambda: take_screenshot("SE38_3_attributes")),
        (300, lambda: print("=== Back to Home ===")),
        (100, lambda: win.router.go_home()),
        (500, lambda: take_screenshot("home_return")),
    ]

    def run_steps():
        if not steps:
            print("All flows complete")
            app.quit()
            return
        delay, fn = steps.pop(0)
        QTimer.singleShot(delay, lambda: (fn(), run_steps()))

    QTimer.singleShot(500, run_steps)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
