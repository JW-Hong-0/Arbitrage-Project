# gui_dashboard.py
# (⭐️ 2025-11-25: 마우스 복사가 가능한 윈도우 GUI 대시보드)

import tkinter as tk
from tkinter import scrolledtext, ttk, messagebox
import logging
import queue
import threading
import asyncio
import sys
import os

# 기존 봇 클래스 임포트
try:
    from arbitrage_bot import ArbitrageBot
except ImportError:
    print("❌ 'arbitrage_bot.py' 파일을 찾을 수 없습니다.")
    sys.exit(1)

# --- 로그 처리기 (Queue Handler) ---
class QueueHandler(logging.Handler):
    """로그를 큐에 담아 GUI로 전달하는 핸들러"""
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue
        # 시간 포맷 설정
        self.setFormatter(logging.Formatter('%(asctime)s - %(message)s', datefmt='%H:%M:%S'))

    def emit(self, record):
        try:
            msg = self.format(record)
            self.log_queue.put(record) # 레코드 자체를 넘겨서 레벨 등 확인
        except Exception:
            self.handleError(record)

# --- 메인 GUI 클래스 ---
class ArbitrageGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Arbitrage Bot Dashboard (HL / GRVT / PAC)")
        self.root.geometry("1300x800")
        
        # 다크 모드 스타일 (유사)
        self.bg_color = "#1e1e1e"
        self.fg_color = "#d4d4d4"
        self.root.configure(bg=self.bg_color)

        # --- 레이아웃 구성 ---
        # 메인 컨테이너 (좌우 분할)
        self.paned_window = ttk.PanedWindow(root, orient=tk.HORIZONTAL)
        self.paned_window.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 1. 왼쪽: 트레이드 로그 (크게)
        self.frame_trade = self.create_log_frame("📈 Trade & Portfolio Logs", "green")
        self.paned_window.add(self.frame_trade, weight=2)
        self.text_trade = self.create_text_widget(self.frame_trade)

        # 오른쪽 컨테이너 (상하 분할)
        self.right_pane = ttk.PanedWindow(self.paned_window, orient=tk.VERTICAL)
        self.paned_window.add(self.right_pane, weight=1)

        # 2. 오른쪽 위: 에러 로그
        self.frame_error = self.create_log_frame("🚨 Error & Network Logs", "red")
        self.right_pane.add(self.frame_error, weight=1)
        self.text_error = self.create_text_widget(self.frame_error)

        # 3. 오른쪽 아래: 시스템 로그
        self.frame_system = self.create_log_frame("⚙️ System & Debug Logs", "cyan")
        self.right_pane.add(self.frame_system, weight=1)
        self.text_system = self.create_text_widget(self.frame_system)

        # --- 하단 컨트롤 패널 ---
        self.control_frame = tk.Frame(root, bg=self.bg_color)
        self.control_frame.pack(fill=tk.X, padx=5, pady=5)

        self.btn_start = tk.Button(self.control_frame, text="▶ 봇 시작", command=self.start_bot, 
                                   bg="#2ecc71", fg="white", font=("Arial", 12, "bold"), width=15)
        self.btn_start.pack(side=tk.LEFT, padx=5)

        self.btn_stop = tk.Button(self.control_frame, text="⏹ 봇 종료", command=self.stop_bot, 
                                  bg="#e74c3c", fg="white", font=("Arial", 12, "bold"), width=15, state=tk.DISABLED)
        self.btn_stop.pack(side=tk.LEFT, padx=5)
        
        self.status_lbl = tk.Label(self.control_frame, text="상태: 대기 중", bg=self.bg_color, fg="white")
        self.status_lbl.pack(side=tk.RIGHT, padx=10)

        # --- 로깅 연결 ---
        self.log_queue = queue.Queue()
        self.queue_handler = QueueHandler(self.log_queue)
        
        # 루트 로거에 핸들러 추가
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        # 기존 핸들러 제거 (터미널 중복 방지)
        for h in root_logger.handlers[:]:
            root_logger.removeHandler(h)
        root_logger.addHandler(self.queue_handler)
        
        # 봇 로거에도 추가
        logging.getLogger("ArbitrageBot").addHandler(self.queue_handler)

        # 봇 관련 변수
        self.bot_thread = None
        self.bot_loop = None
        self.bot_instance = None
        self.is_running = False

        # 주기적 로그 업데이트 시작
        self.root.after(100, self.process_log_queue)

    def create_log_frame(self, title, color):
        frame = tk.LabelFrame(self.paned_window, text=title, bg=self.bg_color, fg=color, font=("Arial", 10, "bold"))
        return frame

    def create_text_widget(self, parent):
        text_area = scrolledtext.ScrolledText(parent, state='disabled', bg="#252526", fg=self.fg_color, 
                                              font=("Consolas", 10), selectbackground="#264f78")
        text_area.pack(fill=tk.BOTH, expand=True)
        # 태그 설정 (색상)
        text_area.tag_config("INFO", foreground="#d4d4d4")
        text_area.tag_config("WARNING", foreground="orange")
        text_area.tag_config("ERROR", foreground="#f44336")
        text_area.tag_config("TRADE", foreground="#4caf50", font=("Consolas", 10, "bold")) # 녹색
        text_area.tag_config("PROFIT", foreground="#00e676", font=("Consolas", 10, "bold")) # 밝은 녹색
        return text_area

    def process_log_queue(self):
        """큐에서 로그를 꺼내 UI에 표시"""
        while not self.log_queue.empty():
            try:
                record = self.log_queue.get_nowait()
                msg = self.queue_handler.format(record)
                raw_msg = record.getMessage()
                
                # 타임스탬프 포함 메시지
                full_msg = f"{msg}\n"
                
                # 분류 로직
                is_trade = any(k in raw_msg for k in ["진입", "청산", "주문 실행", "포트폴리오", "총 자산", "Hold:", "💾"])
                is_error = record.levelno >= logging.WARNING or any(k in raw_msg for k in ["오류", "실패", "Watchdog", "ConnectionClosed", "❌", "🚨"])
                
                # 1. 트레이드 로그
                if is_trade:
                    tag = "PROFIT" if "수익" in raw_msg or "청산" in raw_msg else "TRADE"
                    self.append_text(self.text_trade, full_msg, tag)
                
                # 2. 에러 로그
                elif is_error:
                    self.append_text(self.text_error, full_msg, "ERROR")
                
                # 3. 시스템 로그 (SDK 잡음 필터링)
                else:
                    if "pysdk" in record.name or "websockets" in record.name:
                        pass 
                    else:
                        tag = "INFO"
                        self.append_text(self.text_system, full_msg, tag)
                        
            except queue.Empty:
                break
        
        self.root.after(100, self.process_log_queue)

    def append_text(self, widget, text, tag):
        widget.configure(state='normal')
        widget.insert(tk.END, text, tag)
        widget.see(tk.END) # 자동 스크롤
        widget.configure(state='disabled')

    def start_bot(self):
        if self.is_running: return
        
        self.is_running = True
        self.btn_start.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL)
        self.status_lbl.config(text="상태: 실행 중 🟢", fg="#4caf50")
        
        # 별도 스레드에서 봇 실행
        self.bot_thread = threading.Thread(target=self.run_async_bot, daemon=True)
        self.bot_thread.start()

    def run_async_bot(self):
        """비동기 봇을 실행하는 스레드 함수"""
        try:
            # 새 이벤트 루프 생성
            self.bot_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.bot_loop)
            
            self.bot_instance = ArbitrageBot(self.bot_loop)
            self.bot_loop.run_until_complete(self.bot_instance.start())
        except asyncio.CancelledError:
            logging.info("봇 작업 취소됨")
        except Exception as e:
            logging.error(f"봇 실행 중 치명적 오류: {e}")
        finally:
            self.is_running = False
            # UI 상태 복구 (메인 스레드에서 실행되도록 스케줄링 필요하지만, 간단히 처리)
            # 실제로는 after를 써야 안전함
            self.root.after(0, self.on_bot_stopped)

    def stop_bot(self):
        if not self.is_running or not self.bot_instance: return
        
        self.status_lbl.config(text="상태: 종료 중... 🟠", fg="orange")
        self.btn_stop.config(state=tk.DISABLED)
        
        # 봇 종료 요청 (Thread-safe하게 호출)
        asyncio.run_coroutine_threadsafe(self.bot_instance.stop(), self.bot_loop)

    def on_bot_stopped(self):
        self.is_running = False
        self.btn_start.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)
        self.status_lbl.config(text="상태: 중지됨 🔴", fg="#f44336")
        logging.info("봇이 완전히 종료되었습니다.")

if __name__ == "__main__":
    root = tk.Tk()
    app = ArbitrageGUI(root)
    root.mainloop()