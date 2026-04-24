"""
Vibe Sentinel - 屏幕活动监控报警器
当检测到屏幕空闲超过阈值时自动发出蜂鸣报警
"""

import time
import argparse
import threading
from datetime import datetime
from pynput import mouse, keyboard
import winsound

IDLE_THRESHOLD_DEFAULT = 30
BEEP_FREQUENCY_DEFAULT = 880
BEEP_DURATION_DEFAULT = 200
BEEP_COUNT_DEFAULT = 3
BEEP_INTERVAL_DEFAULT = 0.3


class ActivityMonitor:
    def __init__(self, idle_threshold=IDLE_THRESHOLD_DEFAULT):
        self.idle_threshold = idle_threshold
        self.last_activity_time = time.time()
        self.is_running = False
        self._lock = threading.Lock()

    def record_activity(self):
        with self._lock:
            self.last_activity_time = time.time()

    def get_idle_time(self):
        with self._lock:
            return time.time() - self.last_activity_time

    def is_idle(self):
        return self.get_idle_time() >= self.idle_threshold


class Sentinel:
    def __init__(self, idle_threshold=IDLE_THRESHOLD_DEFAULT,
                 beep_frequency=BEEP_FREQUENCY_DEFAULT,
                 beep_duration=BEEP_DURATION_DEFAULT,
                 beep_count=BEEP_COUNT_DEFAULT,
                 beep_interval=BEEP_INTERVAL_DEFAULT,
                 quiet_mode=False):
        self.monitor = ActivityMonitor(idle_threshold)
        self.beep_frequency = beep_frequency
        self.beep_duration = beep_duration
        self.beep_count = beep_count
        self.beep_interval = beep_interval
        self.quiet_mode = quiet_mode
        self.is_running = False

        self._mouse_listener = None
        self._keyboard_listener = None
        self._monitor_thread = None

    def _on_activity(self, *args):
        self.monitor.record_activity()

    def _beep_alarm(self):
        if self.quiet_mode:
            return
        for i in range(self.beep_count):
            winsound.Beep(self.beep_frequency, self.beep_duration)
            if i < self.beep_count - 1:
                time.sleep(self.beep_interval)

    def _monitor_loop(self):
        alarm_triggered = False
        while self.is_running:
            time.sleep(1)
            if self.monitor.is_idle():
                if not alarm_triggered:
                    self._beep_alarm()
                    alarm_triggered = True
                    idle_time = self.monitor.get_idle_time()
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    print(f"[{timestamp}] 警报: 屏幕已空闲 {idle_time:.1f} 秒")
            else:
                alarm_triggered = False

    def start(self):
        if self.is_running:
            print("Sentinel已经在运行中")
            return

        self.is_running = True
        self.monitor.record_activity()

        self._mouse_listener = mouse.Listener(
            on_move=self._on_activity,
            on_click=self._on_activity,
            on_scroll=self._on_activity
        )
        self._keyboard_listener = keyboard.Listener(
            on_press=self._on_activity,
            on_release=self._on_activity
        )

        self._mouse_listener.start()
        self._keyboard_listener.start()

        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()

        print(f"Vibe Sentinel已启动 - 空闲阈值: {self.monitor.idle_threshold}秒")
        print("按Ctrl+C停止监控")

    def stop(self):
        self.is_running = False
        if self._mouse_listener:
            self._mouse_listener.stop()
        if self._keyboard_listener:
            self._keyboard_listener.stop()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2)
        print("Vibe Sentinel已停止")


def main():
    parser = argparse.ArgumentParser(
        description="Vibe Sentinel - 屏幕活动监控报警器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python vibe_sentinel.py                    # 使用默认设置启动
  python vibe_sentinel.py -t 60              # 设置60秒空闲阈值
  python vibe_sentinel.py -f 1000 -d 500     # 设置1kHz频率,500ms持续时间
  python vibe_sentinel.py -q                 # 静默模式(只记录,不发出蜂鸣)
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

    args = parser.parse_args()

    sentinel = Sentinel(
        idle_threshold=args.threshold,
        beep_frequency=args.frequency,
        beep_duration=args.duration,
        beep_count=args.count,
        beep_interval=args.interval,
        quiet_mode=args.quiet
    )

    try:
        sentinel.start()
        while sentinel.is_running:
            time.sleep(0.5)
    except KeyboardInterrupt:
        sentinel.stop()


if __name__ == "__main__":
    main()
