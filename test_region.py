"""
简单测试：验证区域选择和截图功能
"""
import mss
import numpy as np
from PIL import Image, ImageDraw
import os

def test_monitor_info():
    sct = mss.mss()
    print("=" * 50)
    print("显示器信息:")
    for i, m in enumerate(sct.monitors):
        print(f"  [{i}] {m['width']}x{m['height']} at ({m['left']}, {m['top']})")
    print("=" * 50)
    sct.close()

def test_screenshot():
    sct = mss.mss()
    monitor = sct.monitors[1]
    print(f"\n截取显示器1: {monitor['width']}x{monitor['height']}")
    screenshot = sct.grab(monitor)
    img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
    print(f"截图尺寸: {img.size}")
    img.save("test_screenshot.png")
    print("已保存到 test_screenshot.png")
    sct.close()

def test_region_screenshot():
    print("\n测试区域截图...")
    sct = mss.mss()
    monitor = sct.monitors[1]

    region = (100, 100, 500, 400)
    left, top, right, bottom = region
    left_adj = max(left - monitor['left'], 0)
    top_adj = max(top - monitor['top'], 0)
    right_adj = min(right - monitor['left'], monitor['width'])
    bottom_adj = min(bottom - monitor['top'], monitor['height'])

    print(f"原始区域: {region}")
    print(f"调整后区域: ({left_adj}, {top_adj}, {right_adj}, {bottom_adj})")

    screenshot = sct.grab(monitor)
    img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
    cropped = img.crop((left_adj, top_adj, right_adj, bottom_adj))

    draw = ImageDraw.Draw(cropped)
    draw.rectangle([0, 0, cropped.width-1, cropped.height-1], outline='red', width=3)

    cropped.save("test_region.png")
    print(f"已保存区域截图到 test_region.png (尺寸: {cropped.size})")
    sct.close()

if __name__ == "__main__":
    test_monitor_info()
    test_screenshot()
    test_region_screenshot()
    print("\n所有测试完成!")
