"""
Vibe Sentinel - 屏幕活动监控报警器 (GUI版本)
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
from tkinter import ttk, messagebox, filedialog
from playsound import playsound

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(SCRIPT_DIR, 'vibe_sentinel_error.log')

def log_error(msg):
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
        print(f"[LOG] {msg}")
    except Exception as e:
        print(f"[LOG ERROR] {e}: {msg}")

IDLE_THRESHOLD_DEFAULT = 30
BEEP_FREQUENCY_DEFAULT = 880
BEEP_DURATION_DEFAULT = 200
BEEP_COUNT_DEFAULT = 6
BEEP_INTERVAL_DEFAULT = 0.3
CAPTURE_INTERVAL = 1.0
PIXEL_CHANGE_THRESHOLD = 0.05


class RegionSelector:
    def __init__(self, monitor_num=1):
        self.monitor_num = monitor_num
        self._region = None
        self.sct = mss.mss()
        self.monitor_info = self.sct.monitors[monitor_num]
        log_error(f"RegionSelector init: monitor {monitor_num} = {self.monitor_info}")

    def select(self):
        monitor = self.monitor_info
        screen_width = monitor['width']
        screen_height = monitor['height']
        screen_left = monitor['left']
        screen_top = monitor['top']

        log_error(f"Creating selection window: {screen_width}x{screen_height}+{screen_left}+{screen_top}")

        self._region = None
        
        root = tk.Toplevel()
        root.title("选择区域")
        root.geometry(f"{screen_width}x{screen_height}+{screen_left}+{screen_top}")
        root.attributes('-alpha', 0.3)
        root.attributes('-topmost', True)
        root.configure(bg='gray')

        canvas = tk.Canvas(root, width=screen_width, height=screen_height, bg='gray', highlightthickness=0)
        canvas.pack()
        canvas.create_rectangle(0, 0, screen_width, screen_height, outline='', fill='gray40')

        canvas.create_text(
            screen_width // 2, 20, 
            text=f"拖动选择区域 | {screen_width}x{screen_height} | ESC取消", 
            fill='white', font=('Arial', 14, 'bold')
        )

        rect_id = None
        start_x = 0
        start_y = 0
        is_selecting = False

        def on_mouse_down(event):
            nonlocal start_x, start_y, is_selecting, rect_id
            start_x = event.x
            start_y = event.y
            is_selecting = True
            log_error(f"Mouse down: ({event.x}, {event.y})")
            if rect_id:
                canvas.delete(rect_id)
            rect_id = canvas.create_rectangle(event.x, event.y, event.x, event.y, outline='red', width=3)

        def on_mouse_move(event):
            nonlocal rect_id
            if is_selecting and rect_id:
                canvas.coords(rect_id, start_x, start_y, event.x, event.y)

        def on_mouse_up(event):
            nonlocal is_selecting
            is_selecting = False
            x1 = min(start_x, event.x)
            y1 = min(start_y, event.y)
            x2 = max(start_x, event.x)
            y2 = max(start_y, event.y)
            log_error(f"Mouse up: ({event.x}, {event.y}), size: {x2-x1}x{y2-y1}")
            
            if x2 - x1 > 10 and y2 - y1 > 10:
                self._region = (x1 + screen_left, y1 + screen_top, x2 + screen_left, y2 + screen_top)
                log_error(f"Region SET: {self._region}")
            else:
                log_error("Region too small, NOT set")
            
            log_error(f"About to close window, region={self._region}")
            root.quit()

        canvas.bind('<Button-1>', on_mouse_down)
        canvas.bind('<B1-Motion>', on_mouse_move)
        canvas.bind('<ButtonRelease-1>', on_mouse_up)
        root.bind('<Escape>', lambda e: (log_error("ESC pressed"), root.quit()))
        root.grab_set()
        root.focus_force()
        
        log_error("Starting mainloop...")
        root.mainloop()
        log_error(f"Mainloop ended, region={self._region}")
        
        root.destroy()
        self.sct.close()
        log_error(f"Returning region: {self._region}")
        return self._region


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
        self.root.geometry("500x580")
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
        self.mp3_path = None
        self.mp3_count = 1

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
        self.root.geometry("600x700")
        self.root.resizable(False, False)

        container = ttk.Frame(self.root)
        container.pack(fill='both', expand=True)

        self.canvas = tk.Canvas(container, width=480, height=480, highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient='vertical', command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas, padding="10")

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor='nw', width=460)
        self.canvas.configure(yscrollcommand=scrollbar.set)

        # 绑定鼠标滚轮事件
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        self.canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        ttk.Label(self.scrollable_frame, text="Vibe Sentinel", font=('Arial', 20, 'bold')).pack(pady=(0, 5))
        ttk.Label(self.scrollable_frame, text="屏幕活动监控报警器", font=('Arial', 10)).pack(pady=(0, 10))

        self.info_label = ttk.Label(self.scrollable_frame, text="检测显示器信息中...", font=('Arial', 9), foreground='gray')
        self.info_label.pack(pady=(0, 10))

        region_frame = ttk.LabelFrame(self.scrollable_frame, text="监控区域", padding="10")
        region_frame.pack(fill='x', pady=(0, 10))

        self.region_label = ttk.Label(region_frame, text="未选择区域", foreground='gray')
        self.region_label.pack(side='left', padx=(0, 10))
        self.select_region_btn = ttk.Button(region_frame, text="选择区域", command=self._select_region)
        self.select_region_btn.pack(side='right')

        preview_frame = ttk.LabelFrame(self.scrollable_frame, text="区域预览", padding="5")
        preview_frame.pack(fill='x', pady=(0, 10), ipady=80)
        self.preview_label = ttk.Label(preview_frame, text="选择区域后将显示预览")
        self.preview_label.pack(expand=True)

        settings_frame = ttk.LabelFrame(self.scrollable_frame, text="监控设置", padding="10")
        settings_frame.pack(fill='x', pady=(0, 10))

        threshold_row = ttk.Frame(settings_frame)
        threshold_row.pack(fill='x', pady=2)
        ttk.Label(threshold_row, text="空闲阈值 (秒):").pack(side='left')
        self.threshold_var = tk.IntVar(value=self.threshold)
        ttk.Spinbox(threshold_row, from_=5, to=300, width=8, textvariable=self.threshold_var).pack(side='right')

        # 隐藏蜂鸣设置
        # beep_row = ttk.Frame(settings_frame)
        # beep_row.pack(fill='x', pady=2)
        # ttk.Label(beep_row, text="蜂鸣频率 (Hz):").pack(side='left')
        # self.freq_var = tk.IntVar(value=self.frequency)
        # ttk.Spinbox(beep_row, from_=200, to=2000, width=8, textvariable=self.freq_var).pack(side='right')

        # count_row = ttk.Frame(settings_frame)
        # count_row.pack(fill='x', pady=2)
        # ttk.Label(count_row, text="蜂鸣次数:").pack(side='left')
        # self.count_var = tk.IntVar(value=self.count)
        # ttk.Spinbox(count_row, from_=1, to=10, width=8, textvariable=self.count_var).pack(side='right')

        monitor_row = ttk.Frame(settings_frame)
        monitor_row.pack(fill='x', pady=2)
        ttk.Label(monitor_row, text="显示器编号:").pack(side='left')
        self.monitor_var = tk.IntVar(value=self.monitor_num)
        ttk.Spinbox(monitor_row, from_=1, to=10, width=8, textvariable=self.monitor_var).pack(side='right')

        mp3_row = ttk.Frame(settings_frame)
        mp3_row.pack(fill='x', pady=2)
        ttk.Label(mp3_row, text="自定义MP3:").pack(side='left')
        self.mp3_var = tk.StringVar(value="")
        ttk.Entry(mp3_row, textvariable=self.mp3_var, width=20).pack(side='left', padx=(0, 5))
        ttk.Button(mp3_row, text="浏览", command=self._browse_mp3).pack(side='right')

        mp3_count_row = ttk.Frame(settings_frame)
        mp3_count_row.pack(fill='x', pady=2)
        ttk.Label(mp3_count_row, text="MP3播放次数:").pack(side='left')
        self.mp3_count_var = tk.IntVar(value=1)
        ttk.Spinbox(mp3_count_row, from_=1, to=10, width=8, textvariable=self.mp3_count_var).pack(side='right')

        control_frame = ttk.Frame(self.scrollable_frame)
        control_frame.pack(fill='x', pady=(10, 0))
        self.status_label = ttk.Label(control_frame, text="状态: 待机", foreground='gray')
        self.status_label.pack(side='left', pady=(0, 10))
        # ttk.Button(control_frame, text="测试蜂鸣", command=self._test_beep).pack(side='right', padx=(0, 5))
        ttk.Button(control_frame, text="测试MP3", command=self._test_mp3).pack(side='right', padx=(0, 5))
        self.start_btn = ttk.Button(control_frame, text="开始监控", command=self._start)
        self.start_btn.pack(side='right', padx=(0, 5))
        self.stop_btn = ttk.Button(control_frame, text="停止监控", command=self._stop, state='disabled')
        self.stop_btn.pack(side='right', padx=(0, 5))

    def _select_region(self):
        self.monitor_num = self.monitor_var.get()
        log_error(f"_select_region called, monitor_num={self.monitor_num}")
        try:
            selector = RegionSelector(self.monitor_num)
            region = selector.select()
            log_error(f"_select_region returned: {region}")
            if region:
                self.region = region
                self.region_label.config(text=f"({region[0]}, {region[1]}) -> ({region[2]}, {region[3]})")
                log_error(f"UI updated with region: {region}")
                self._update_preview()
            else:
                log_error("Region is None, UI NOT updated")
        except Exception as e:
            log_error(f"_select_region ERROR: {e}")
            messagebox.showerror("错误", f"选择区域失败: {e}")

    def _update_preview(self):
        if not self.region:
            log_error("_update_preview: no region")
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
            log_error("_update_preview: SUCCESS")
        except Exception as e:
            log_error(f"_update_preview ERROR: {e}")
            self.preview_label.config(text=f"预览失败: {e}")

    def _beep_alarm(self):
        log_error(f"_beep_alarm called: frequency={self.frequency}, duration={self.duration}, count={self.count}")
        try:
            for i in range(self.count):
                log_error(f"Beep {i+1}/{self.count}: {self.frequency}Hz for {self.duration}ms")
                winsound.Beep(self.frequency, self.duration)
                if i < self.count - 1:
                    time.sleep(BEEP_INTERVAL_DEFAULT)
        except Exception as e:
            log_error(f"_beep_alarm error: {e}")

    def _test_beep(self):
        log_error("_test_beep called")
        # 获取当前设置的参数
        self.threshold = self.threshold_var.get()
        self.frequency = self.freq_var.get()
        self.count = self.count_var.get()
        self.monitor_num = self.monitor_var.get()
        # 测试蜂鸣
        self._beep_alarm()

    def _browse_mp3(self):
        log_error("_browse_mp3 called")
        file_path = filedialog.askopenfilename(
            title="选择MP3文件",
            filetypes=[("MP3文件", "*.mp3"), ("所有文件", "*.*")]
        )
        if file_path:
            self.mp3_var.set(file_path)
            self.mp3_path = file_path
            log_error(f"MP3文件选择: {file_path}")

    def _test_mp3(self):
        log_error("_test_mp3 called")
        # 获取当前设置的MP3路径和次数
        self.mp3_path = self.mp3_var.get()
        self.mp3_count = self.mp3_count_var.get()
        if self.mp3_path and os.path.exists(self.mp3_path):
            log_error(f"测试MP3: {self.mp3_path}, 次数: {self.mp3_count}")
            try:
                # 在后台线程中播放MP3
                def play_mp3():
                    try:
                        for i in range(self.mp3_count):
                            log_error(f"播放MP3 {i+1}/{self.mp3_count}")
                            playsound(self.mp3_path)
                            if i < self.mp3_count - 1:
                                time.sleep(0.5)  # 间隔0.5秒
                    except Exception as e:
                        log_error(f"播放MP3失败: {e}")
                        messagebox.showerror("错误", f"播放MP3失败: {e}")
                
                threading.Thread(target=play_mp3, daemon=True).start()
            except Exception as e:
                log_error(f"测试MP3错误: {e}")
                messagebox.showerror("错误", f"测试MP3失败: {e}")
        else:
            messagebox.showwarning("警告", "请先选择有效的MP3文件")

    def _on_mousewheel(self, event):
        # 处理鼠标滚轮事件
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def _monitor_loop(self):
        while self.is_running:
            time.sleep(CAPTURE_INTERVAL)
            if not self.region:
                continue
            try:
                # 再次检查 is_running，因为可能在 sleep 期间被设置为 False
                if not self.is_running:
                    break
                
                has_activity, _ = self.monitor.capture_and_compare()
                if has_activity:
                    self.idle_start_time = None
                    self.alarm_triggered = False
                else:
                    if self.idle_start_time is None:
                        self.idle_start_time = time.time()
                    idle_time = time.time() - self.idle_start_time
                    if idle_time >= self.threshold and not self.alarm_triggered:
                        self.alarm_triggered = True
                        # 优先使用MP3
                        if self.mp3_path and os.path.exists(self.mp3_path):
                            log_error(f"播放MP3警报: {self.mp3_path}, 次数: {self.mp3_count}")
                            try:
                                def play_mp3():
                                    try:
                                        for i in range(self.mp3_count):
                                            # 检查是否仍然需要播放
                                            if not self.is_running:
                                                break
                                            log_error(f"播放MP3 {i+1}/{self.mp3_count}")
                                            playsound(self.mp3_path)
                                            if i < self.mp3_count - 1:
                                                time.sleep(0.5)  # 间隔0.5秒
                                    except Exception as e:
                                        log_error(f"播放MP3失败: {e}")
                                
                                threading.Thread(target=play_mp3, daemon=True).start()
                            except Exception as e:
                                log_error(f"MP3播放错误: {e}")
                                # 失败时回退到蜂鸣
                                # self._beep_alarm()
                        else:
                            # 隐藏蜂鸣功能
                            log_error("未设置MP3文件")
            except Exception as e:
                log_error(f"_monitor_loop error: {e}")
                # 如果发生错误，短暂休眠后继续
                time.sleep(1)
        if self.monitor:
            self.monitor.close()

    def _start(self):
        if not self.region:
            messagebox.showwarning("请先选择区域", "请先点击选择区域按钮")
            return
        self.threshold = self.threshold_var.get()
        # self.frequency = self.freq_var.get()
        # self.count = self.count_var.get()
        self.monitor_num = self.monitor_var.get()
        self.mp3_path = self.mp3_var.get()
        self.mp3_count = self.mp3_count_var.get()
        try:
            self.monitor = ScreenMonitor(self.monitor_num, self.region)
            self.is_running = True
            self.idle_start_time = None
            self.alarm_triggered = False
            self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.monitor_thread.start()
            self.start_btn.config(state='disabled')
            self.stop_btn.config(state='normal')
            self.select_region_btn.config(state='disabled')  # 禁止重新框选
            self.status_label.config(text="状态: 监控中", foreground='green')
            # 启动状态更新循环
            self._update_status()
        except Exception as e:
            log_error(f"_start error: {e}")
            messagebox.showerror("错误", f"启动监控失败: {e}")
    
    def _update_status(self):
        """定期更新监控状态"""
        if not self.is_running:
            return
        
        try:
            # 计算当前空闲时间
            idle_time = time.time() - self.idle_start_time if self.idle_start_time else 0
            
            # 根据状态更新UI
            if not self.alarm_triggered:
                if idle_time > 0:
                    self.status_label.config(text=f"状态: 画面静止 {int(idle_time)} 秒", foreground='orange')
                else:
                    self.status_label.config(text="状态: 监控中 (有活动)", foreground='green')
            else:
                self.status_label.config(text=f"警报: 画面静止 {int(idle_time)} 秒!", foreground='red')
                
            # 继续定时更新
            if self.is_running:
                self.root.after(1000, self._update_status)  # 每秒更新一次
        except Exception as e:
            log_error(f"_update_status error: {e}")
            # 即使出错也继续尝试更新
            if self.is_running:
                self.root.after(1000, self._update_status)

    def _stop(self):
        self.is_running = False
        if self.monitor:
            self.monitor.close()
            self.monitor = None
        self.start_btn.config(state='normal')
        self.stop_btn.config(state='disabled')
        self.select_region_btn.config(state='normal')  # 允许重新框选
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