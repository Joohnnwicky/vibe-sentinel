"""
Vibe Sentinel - 屏幕活动监控报警器
监控屏幕画面变化，当检测到画面静止超过阈值时自动发出蜂鸣报警
用于检测Claude Code等AI助手是否在等待用户决策
"""

import time
import argparse
import threading
from datetime import datetime
import winsound
import mss
import numpy as np
from PIL import Image

IDLE_THRESHOLD_DEFAULT = 30
BEEP_FREQUENCY_DEFAULT = 880
BEEP_DURATION_DEFAULT = 200
BEEP_COUNT_DEFAULT = 3
BEEP_INTERVAL_DEFAULT = 0.3
CAPTURE_INTERVAL = 1.0
PIXEL_CHANGE_THRESHOLD = 0.05


class ScreenMonitor:
    def __init__(self, monitor_num=1, region=None):
        self.monitor_num = monitor_num
        self.region = region
        self.sct = mss.mss()
        self.last_screenshot = None
        self._lock = threading.Lock()

    def _get_pixels(self, screenshot):
        if self.region:
            return np.array(screenshot.crop(self.region))[:, :, :3]
        else:
            monitor = self.sct.monitors[self.monitor_num]
            bbox = (monitor["left"], monitor["top"], monitor["width"], monitor["height"])
            return np.array(screenshot.crop(bbox))[:, :, :3]

    def _compute_difference(self, img1, img2):
        if img1.shape != img2.shape:
            return float('inf')
        diff = np.abs(img1.astype(np.int16) - img2.astype(np.int16))
        return np.mean(diff)

    def capture_and_compare(self):
        screenshot = self.sct.grab(self.sct.monitors[self.monitor_num])
        img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
        pixels = self._get_pixels(img)

        with self._lock:
            if self.last_screenshot is None:
                self.last_screenshot = pixels
                return True

            diff = self._compute_difference(self.last_screenshot, pixels)
            self.last_screenshot = pixels

            return diff > PIXEL_CHANGE_THRESHOLD


class Sentinel:
    def __init__(self, idle_threshold=IDLE_THRESHOLD_DEFAULT,
                 beep_frequency=BEEP_FREQUENCY_DEFAULT,
                 beep_duration=BEEP_DURATION_DEFAULT,
                 beep_count=BEEP_COUNT_DEFAULT,
                 beep_interval=BEEP_INTERVAL_DEFAULT,
                 quiet_mode=False,
                 monitor_num=1,
                 region=None):
        self.monitor = ScreenMonitor(monitor_num, region)
        self.idle_threshold = idle_threshold
        self.beep_frequency = beep_frequency
        self.beep_duration = beep_duration
        self.beep_count = beep_count
        self.beep_interval = beep_interval
        self.quiet_mode = quiet_mode
        self.is_running = False

        self.last_activity_time = time.time()
        self._monitor_thread = None
        self._alarm_triggered = False

    def record_activity(self):
        self.last_activity_time = time.time()
        self._alarm_triggered = False

    def get_idle_time(self):
        return time.time() - self.last_activity_time

    def is_idle(self):
        return self.get_idle_time() >= self.idle_threshold

    def _beep_alarm(self):
        if self.quiet_mode:
            return
        for i in range(self.beep_count):
            winsound.Beep(self.beep_frequency, self.beep_duration)
            if i < self.beep_count - 1:
                time.sleep(self.beep_interval)

    def _monitor_loop(self):
        while self.is_running:
            time.sleep(CAPTURE_INTERVAL)

            has_activity = self.monitor.capture_and_compare()
            if has_activity:
                self.record_activity()
            else:
                if self.is_idle() and not self._alarm_triggered:
                    self._beep_alarm()
                    self._alarm_triggered = True
                    idle_time = self.get_idle_time()
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    print(f"[{timestamp}] 警报: 画面静止 {idle_time:.1f} 秒")

    def start(self):
        if self.is_running:
            print("Sentinel已经在运行中")
            return

        self.is_running = True
        self.record_activity()

        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()

        print(f"Vibe Sentinel已启动 - 空闲阈值: {self.idle_threshold}秒")
        print(f"监控屏幕 #{self.monitor.monitor_num}")
        print("按Ctrl+C停止监控")

    def stop(self):
        self.is_running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2)
        print("Vibe Sentinel已停止")


def main():
    parser = argparse.ArgumentParser(
        description="Vibe Sentinel - 屏幕画面活动监控报警器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python vibe_sentinel.py                    # 使用默认设置启动
  python vibe_sentinel.py -t 60              # 设置60秒空闲阈值
  python vibe_sentinel.py -f 1000 -d 500     # 设置1kHz频率,500ms持续时间
  python vibe_sentinel.py -q                 # 静默模式(只记录,不发出蜂鸣)
  python vibe_sentinel.py -m 2               # 监控第二个显示器
        """
    )

    parser.add_argument('-t', '--threshold', type=int, default=IDLE_THRESHOLD_DEFAULT,
                        help=f'空闲超时阈值(秒), 默认: {IDLE_THRESHOLD_DEFAULT}')
    parser.add_argument('-f', '--frequency', type=int, default=BEEP_FREQUENCY_DEFAULT,
                        help=f'蜂鸣频率(Hz), 默认: {BEEP_FREQUENCY_DEFAULT}')
    parser.add_argument('-d', '--duration', type=int, default=BEEP_DURATION_DEFAULT,
                        help=f'蜂鸣持续时间(ms), 默认: {BEEP_DURATION_DEFAULT}')
    parser.add_argument('-c', '--count', type=int, default=BEEP_COUNT_DEFAULT,
                        help=f'蜂鸣次数, 默认: {BEEP_COUNT_DEFAULT}')
    parser.add_argument('-i', '--interval', type=float, default=BEEP_INTERVAL_DEFAULT,
                        help=f'蜂鸣间隔(秒), 默认: {BEEP_INTERVAL_DEFAULT}')
    parser.add_argument('-q', '--quiet', action='store_true',
                        help='静默模式: 不发出蜂鸣,只在控制台输出')
    parser.add_argument('-m', '--monitor', type=int, default=1,
                        help='监控的显示器编号, 默认: 1')

    args = parser.parse_args()

    sentinel = Sentinel(
        idle_threshold=args.threshold,
        beep_frequency=args.frequency,
        beep_duration=args.duration,
        beep_count=args.count,
        beep_interval=args.interval,
        quiet_mode=args.quiet,
        monitor_num=args.monitor
    )

    try:
        sentinel.start()
        while sentinel.is_running:
            time.sleep(0.5)
    except KeyboardInterrupt:
        sentinel.stop()


if __name__ == "__main__":
    main()
