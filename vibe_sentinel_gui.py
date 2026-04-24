"""
Vibe Sentinel - 屏幕活动监控报警器 (GUI版本)
监控屏幕画面变化，当检测到画面静止超过阈值时自动发出蜂鸣报警
用于检测Claude Code等AI助手是否在等待用户决策
"""

import time
import threading
import sys
import os
from datetime import datetime
import winsound
import mss
import numpy as np
from PIL import Image, ImageTk, ImageDraw
import tkinter as tk
from tkinter import ttk, messagebox

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(sys.executable)), 'vibe_sentinel_error.log')

def log_error(msg):
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except:
        pass

IDLE_THRESHOLD_DEFAULT = 30
BEEP_FREQUENCY_DEFAULT = 880
BEEP_DURATION_DEFAULT = 200
BEEP_COUNT_DEFAULT = 3
BEEP_INTERVAL_DEFAULT = 0.3
CAPTURE_INTERVAL = 1.0
PIXEL_CHANGE_THRESHOLD = 0.05


class RegionSelector:
    def __init__(self, monitor_num=1):
        self.monitor_num = monitor_num
        self.region = None
        self.sct = mss.mss()
        self.monitor_info = self.sct.monitors[monitor_num]
        log_error(f"Monitor {monitor_num} info: {self.monitor_info}")

    def select(self):
        monitor = self.monitor_info
        screen_width = monitor['width']
        screen_height = monitor['height']
        screen_left = monitor['left']
        screen_top = monitor['top']

        log_error(f"Creating selection window: {screen_width}x{screen_height}+{screen_left}+{screen_top}")

        root = tk.Toplevel()
        root.geometry(f"{screen_width}x{screen_height}+{screen_left}+{screen_top}")
        root.attributes('-alpha', 0.3)
        root.attributes('-topmost', True)
        root.configure(bg='gray')

        canvas = tk.Canvas(root, width=screen_width, height=screen_height, bg='gray', highlightthickness=0)
        canvas.pack()
        canvas.create_rectangle(0, 0, screen_width, screen_height, outline='', fill='gray40')

        rect_id = [None]
        instruction_text_id = [None]
        selection_data = {'start_x': 0, 'start_y': 0, 'is_selecting': False}

        def update_instruction():
            text = f"拖动选择区域 | {screen_width}x{screen_height} | ESC取消"
            if instruction_text_id[0]:
                canvas.itemconfig(instruction_text_id[0], text=text)
            else:
                instruction_text_id[0] = canvas.create_text(
                    screen_width // 2, 20, text=text, fill='white', font=('Arial', 14, 'bold'))

        def on_mouse_down(event):
            selection_data['start_x'] = event.x
            selection_data['start_y'] = event.y
            selection_data['is_selecting'] = True
            if rect_id[0]:
                canvas.delete(rect_id[0])
            rect_id[0] = canvas.create_rectangle(event.x, event.y, event.x, event.y, outline='red', width=3)
            update_instruction()

        def on_mouse_move(event):
            if selection_data['is_selecting'] and rect_id[0]:
                canvas.coords(rect_id[0], selection_data['start_x'], selection_data['start_y'], event.x, event.y)

        def on_mouse_up(event):
            selection_data['is_selecting'] = False
            x1 = min(selection_data['start_x'], event.x)
            y1 = min(selection_data['start_y'], event.y)
            x2 = max(selection_data['start_x'], event.x)
            y2 = max(selection_data['start_y'], event.y)
            if x2 - x1 > 10 and y2 - y1 > 10:
                self.region = (x1 + screen_left, y1 + screen_top, x2 + screen_left, y2 + screen_top)
                log_error(f"Region selected: {self.region}")
            root.destroy()

        canvas.bind('<Button-1>', on_mouse_down)
        canvas.bind('<B1-Motion>', on_mouse_move)
        canvas.bind('<ButtonRelease-1>', on_mouse_up)
        root.bind('<Escape>', lambda e: root.destroy())
        root.grab_set()
        update_instruction()
        root.mainloop()
        self.sct.close()
        return self.region


class ScreenMonitor:
    def __init__(self, monitor_num=1, region=None):
        self.monitor_num = monitor_num
        self.region = region
        self.sct = mss.mss()
        self.last_screenshot = None
        self._lock = threading.Lock()
        self._monitor_info = self.sct.monitors[monitor_num]

    @property
    def monitor_info(self):
        return {
            'left': self._monitor_info['left'],
            'top': self._monitor_info['top'],
            'width': self._monitor_info['width'],
            'height': self._monitor_info['height']
        }

    def capture_and_compare(self):
        monitor = self.sct.monitors[self.monitor_num]
        screenshot = self.sct.grab(monitor)
        img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")

        if self.region:
            left, top, right, bottom = self.region
            left = max(left - monitor['left'], 0)
            top = max(top - monitor['top'], 0)
            right = min(right - monitor['left'], monitor['width'])
            bottom = min(bottom - monitor['top'], monitor['height'])
            img = img.crop((left, top, right, bottom))

        pixels = np.array(img)[:, :, :3]

        with self._lock:
            if self.last_screenshot is None:
                self.last_screenshot = pixels
                return True, img

            diff = np.abs(pixels.astype(np.int16) - self.last_screenshot.astype(np.int16))
            mean_diff = np.mean(diff)
            self.last_screenshot = pixels

            return mean_diff > PIXEL_CHANGE_THRESHOLD, img

    def close(self):
        self.sct.close()


class SentinelApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Vibe Sentinel - 屏幕活动监控")
        self.root.geometry("500x420")
        self.root.resizable(False, False)

        self.monitor_num = 1
        self.region = None
        self.is_running = False
        self.monitor = None
        self.monitor_thread = None
        self.idle_start_time = None
        self.alarm_triggered = False

        self.threshold = IDLE_THRESHOLD_DEFAULT
        self.frequency = BEEP_FREQUENCY_DEFAULT
        self.duration = BEEP_DURATION_DEFAULT
        self.count = BEEP_COUNT_DEFAULT

        self._setup_ui()
        self._show_monitor_info()

    def _show_monitor_info(self):
        try:
            sct = mss.mss()
            monitors = sct.monitors
            info_text = f"检测到 {len(monitors)-1} 个显示器\n"
            for i, m in enumerate(monitors[1:], 1):
                info_text += f"  显示器{i}: {m['width']}x{m['height']} at ({m['left']}, {m['top']})\n"
            self.info_label.config(text=info_text.strip())
            sct.close()
        except Exception as e:
            log_error(f"_show_monitor_info error: {e}")

    def _setup_ui(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Vibe Sentinel", font=('Arial', 20, 'bold')).pack(pady=(0, 5))
        ttk.Label(main_frame, text="屏幕活动监控报警器", font=('Arial', 10)).pack(pady=(0, 10))

        self.info_label = ttk.Label(main_frame, text="检测显示器信息中...", font=('Arial', 9), foreground='gray')
        self.info_label.pack(pady=(0, 10))

        region_frame = ttk.LabelFrame(main_frame, text="监控区域", padding="10")
        region_frame.pack(fill='x', pady=(0, 10))

        self.region_label = ttk.Label(region_frame, text="未选择区域", foreground='gray')
        self.region_label.pack(side='left', padx=(0, 10))
        ttk.Button(region_frame, text="📐 选择区域", command=self._select_region).pack(side='right')

        preview_frame = ttk.LabelFrame(main_frame, text="区域预览", padding="5")
        preview_frame.pack(fill='both', expand=True, pady=(0, 10))
        self.preview_label = ttk.Label(preview_frame, text="选择区域后将显示预览")
        self.preview_label.pack(expand=True)

        settings_frame = ttk.LabelFrame(main_frame, text="监控设置", padding="10")
        settings_frame.pack(fill='x', pady=(0, 10))

        threshold_row = ttk.Frame(settings_frame)
        threshold_row.pack(fill='x', pady=2)
        ttk.Label(threshold_row, text="空闲阈值 (秒):").pack(side='left')
        self.threshold_var = tk.IntVar(value=self.threshold)
        ttk.Spinbox(threshold_row, from_=5, to=300, width=8, textvariable=self.threshold_var).pack(side='right')

        beep_row = ttk.Frame(settings_frame)
        beep_row.pack(fill='x', pady=2)
        ttk.Label(beep_row, text="蜂鸣频率 (Hz):").pack(side='left')
        self.freq_var = tk.IntVar(value=self.frequency)
        ttk.Spinbox(beep_row, from_=200, to=2000, width=8, textvariable=self.freq_var).pack(side='right')

        count_row = ttk.Frame(settings_frame)
        count_row.pack(fill='x', pady=2)
        ttk.Label(count_row, text="蜂鸣次数:").pack(side='left')
        self.count_var = tk.IntVar(value=self.count)
        ttk.Spinbox(count_row, from_=1, to=10, width=8, textvariable=self.count_var).pack(side='right')

        monitor_row = ttk.Frame(settings_frame)
        monitor_row.pack(fill='x', pady=2)
        ttk.Label(monitor_row, text="显示器编号:").pack(side='left')
        self.monitor_var = tk.IntVar(value=self.monitor_num)
        ttk.Spinbox(monitor_row, from_=1, to=10, width=8, textvariable=self.monitor_var).pack(side='right')

        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill='x')
        self.status_label = ttk.Label(control_frame, text="状态: 待机", foreground='gray')
        self.status_label.pack(side='left', pady=(0, 10))
        self.start_btn = ttk.Button(control_frame, text="▶ 开始监控", command=self._start)
        self.start_btn.pack(side='right')
        self.stop_btn = ttk.Button(control_frame, text="⏹ 停止监控", command=self._stop, state='disabled')
        self.stop_btn.pack(side='right', padx=(0, 5))

    def _select_region(self):
        self.monitor_num = self.monitor_var.get()
        try:
            selector = RegionSelector(self.monitor_num)
            region = selector.select()
            if region:
                self.region = region
                self.region_label.config(text=f"({region[0]}, {region[1]}) → ({region[2]}, {region[3]})")
                self._update_preview()
        except Exception as e:
            log_error(f"_select_region error: {e}")
            messagebox.showerror("错误", f"选择区域失败: {e}")

    def _update_preview(self):
        if not self.region:
            return
        try:
            sct = mss.mss()
            monitor = sct.monitors[self.monitor_num]
            screenshot = sct.grab(monitor)
            img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")

            left, top, right, bottom = self.region
            left = max(left - monitor['left'], 0)
            top = max(top - monitor['top'], 0)
            right = min(right - monitor['left'], monitor['width'])
            bottom = min(bottom - monitor['top'], monitor['height'])
            img = img.crop((left, top, right, bottom))

            ratio = img.width / img.height if img.height > 0 else 1
            preview_width = 300
            preview_height = int(preview_width / ratio)
            img = img.resize((preview_width, preview_height), Image.Resampling.LANCZOS)

            draw = ImageDraw.Draw(img)
            draw.rectangle([0, 0, img.width-1, img.height-1], outline='red', width=3)

            self.preview_photo = ImageTk.PhotoImage(img)
            self.preview_label.config(image=self.preview_photo, text="")
            sct.close()
        except Exception as e:
            log_error(f"_update_preview error: {e}")
            self.preview_label.config(text=f"预览失败: {e}")

    def _beep_alarm(self):
        try:
            for i in range(self.count):
                winsound.Beep(self.frequency, self.duration)
                if i < self.count - 1:
                    time.sleep(BEEP_INTERVAL_DEFAULT)
        except Exception as e:
            log_error(f"_beep_alarm error: {e}")

    def _monitor_loop(self):
        while self.is_running:
            time.sleep(CAPTURE_INTERVAL)
            if not self.region:
                continue
            try:
                has_activity, _ = self.monitor.capture_and_compare()
                if has_activity:
                    self.idle_start_time = None
                    self.alarm_triggered = False
                    self.root.after(0, lambda: self.status_label.config(text="状态: 监控中 (有活动)", foreground='green'))
                else:
                    idle_time = time.time() - self.idle_start_time if self.idle_start_time else 0
                    self.root.after(0, lambda t=idle_time: self.status_label.config(text=f"状态: 画面静止 {int(t)} 秒", foreground='orange'))
                    if self.idle_start_time is None:
                        self.idle_start_time = time.time()
                    if idle_time >= self.threshold and not self.alarm_triggered:
                        self.alarm_triggered = True
                        self._beep_alarm()
                        self.root.after(0, lambda: self.status_label.config(text=f"⚠️ 警报: 画面静止 {int(idle_time)} 秒!", foreground='red'))
            except Exception as e:
                log_error(f"_monitor_loop error: {e}")
        if self.monitor:
            self.monitor.close()

    def _start(self):
        if not self.region:
            messagebox.showwarning("请先选择区域", "请先点击「选择区域」按钮")
            return
        self.threshold = self.threshold_var.get()
        self.frequency = self.freq_var.get()
        self.count = self.count_var.get()
        self.monitor_num = self.monitor_var.get()
        try:
            self.monitor = ScreenMonitor(self.monitor_num, self.region)
            self.is_running = True
            self.idle_start_time = None
            self.alarm_triggered = False
            self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.monitor_thread.start()
            self.start_btn.config(state='disabled')
            self.stop_btn.config(state='normal')
            self.status_label.config(text="状态: 监控中", foreground='green')
        except Exception as e:
            log_error(f"_start error: {e}")
            messagebox.showerror("错误", f"启动监控失败: {e}")

    def _stop(self):
        self.is_running = False
        if self.monitor:
            self.monitor.close()
            self.monitor = None
        self.start_btn.config(state='normal')
        self.stop_btn.config(state='disabled')
        self.status_label.config(text="状态: 已停止", foreground='gray')

    def on_closing(self):
        self.is_running = False
        if self.monitor:
            self.monitor.close()
        self.root.destroy()


def main():
    try:
        root = tk.Tk()
        app = SentinelApp(root)
        root.protocol("WM_DELETE_WINDOW", app.on_closing)
        root.mainloop()
    except Exception as e:
        log_error(f"main error: {e}")
        raise


if __name__ == "__main__":
    main()
