import tkinter as tk
from tkinter import ttk, scrolledtext
import asyncio
import logging
import queue
import threading
import sys
import time
from datetime import datetime

# 기존 봇 모듈 임포트
try:
    from arbitrage_bot import ArbitrageBot
    import settings  
except ImportError:
    print("❌ 'arbitrage_bot.py' 또는 'settings.py'를 찾을 수 없습니다.")
    sys.exit(1)

# --- 로그 필터링 ---
logging.getLogger("pysdk").setLevel(logging.WARNING)
logging.getLogger("GrvtCcxtWS").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("websockets").setLevel(logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.WARNING)

# --- 로그 핸들러 ---
class QueueHandler(logging.Handler):
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue
        self.setFormatter(logging.Formatter('%(asctime)s - %(message)s', datefmt='%H:%M:%S'))

    def emit(self, record):
        try:
            if "GrvtCcxtWS" in record.name: return
            msg = self.format(record)
            self.log_queue.put((record.levelno, msg, record.message))
        except Exception:
            self.handleError(record)

class ArbitrageDashboard:
    def __init__(self, root):
        self.root = root
        self.root.title("🚀 5-Exchange Arbitrage Bot V16 (HL/GRVT/PAC/EXT/LTR)")
        self.root.geometry("1400x900")
        
        # 다크 테마 스타일
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Treeview", background="#2b2b2b", fieldbackground="#2b2b2b", foreground="white", rowheight=25)
        style.configure("Treeview.Heading", background="#444", foreground="white", font=('Arial', 10, 'bold'))
        style.map("Treeview", background=[('selected', '#0078d7')])

        # 변수 초기화
        self.is_running = False
        self.log_queue = queue.Queue()
        self.bot_loop = None
        self.bot_instance = None
        
        # GUI 레이아웃 구성
        self._setup_ui()
        self._setup_logging()
        
        # 주기적 업데이트 시작
        self.root.after(100, self._process_logs)
        self.root.after(1000, self._update_market_data) # 1초마다 데이터 갱신

    def _setup_ui(self):
        # 상단 컨트롤 패널
        control_frame = ttk.Frame(self.root, padding="10")
        control_frame.pack(fill=tk.X)
        
        self.btn_start = ttk.Button(control_frame, text="▶ Start Bot", command=self.start_bot)
        self.btn_start.pack(side=tk.LEFT, padx=5)
        
        self.btn_stop = ttk.Button(control_frame, text="⏹ Stop Bot", command=self.stop_bot, state="disabled")
        self.btn_stop.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(control_frame, text=" |  Risk Limit: ").pack(side=tk.LEFT)
        self.lbl_status = ttk.Label(control_frame, text="READY", foreground="orange", font=('Arial', 10, 'bold'))
        self.lbl_status.pack(side=tk.LEFT)

        # 메인 컨텐츠 (좌우 분할)
        paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # 왼쪽: 마켓 데이터 테이블
        left_frame = ttk.LabelFrame(paned, text="📊 Real-time Market Spread", padding="5")
        paned.add(left_frame, weight=2)
        
        cols = ("Ticker", "HL", "GRVT", "PAC", "EXT", "LTR", "Spread", "Status")
        self.tree = ttk.Treeview(left_frame, columns=cols, show="headings", selectmode="browse")
        
        # 컬럼 설정
        col_widths = [80, 80, 80, 80, 80, 80, 80, 80]
        for col, width in zip(cols, col_widths):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=width, anchor="center")
            
        # 스크롤바
        vsb = ttk.Scrollbar(left_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 오른쪽: 로그 및 포트폴리오
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=1)
        
        # 로그창
        log_group = ttk.LabelFrame(right_frame, text="📜 System Log")
        log_group.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
        self.log_area = scrolledtext.ScrolledText(log_group, height=15, state='disabled', bg="#1e1e1e", fg="#00ff00", font=('Consolas', 9))
        self.log_area.pack(fill=tk.BOTH, expand=True)

    def _setup_logging(self):
        queue_handler = QueueHandler(self.log_queue)
        logging.getLogger().addHandler(queue_handler)

    def _process_logs(self):
        while not self.log_queue.empty():
            level, msg, raw_msg = self.log_queue.get()
            self.log_area.config(state='normal')
            
            tag = "INFO"
            if level >= logging.ERROR: tag = "ERROR"
            elif level >= logging.WARNING: tag = "WARN"
            elif "체결" in raw_msg: tag = "TRADE"
            
            self.log_area.insert(tk.END, msg + "\n", tag)
            self.log_area.see(tk.END)
            self.log_area.config(state='disabled')
            
        self.root.after(100, self._process_logs)

    def _update_market_data(self):
        """
        [핵심 수정] 봇의 market_cache 데이터를 가져와서 GUI 테이블 갱신
        """
        if not self.bot_instance or not self.is_running:
            self.root.after(1000, self._update_market_data)
            return

        try:
            # 봇의 데이터 캐시 접근 (스레드 안전을 위해 copy 권장하지만 읽기만 하므로 직접 접근)
            # 구조: bot.market_cache[ticker][exchange] = {'bid': ..., 'ask': ...}
            cache = self.bot_instance.market_cache
            
            # 트리뷰 초기화 (또는 기존 항목 업데이트 - 여기선 전체 삭제 후 재생성 방식 사용)
            # 성능 최적화를 위해선 기존 아이템을 업데이트(item_id 사용)하는게 좋음
            for item in self.tree.get_children():
                self.tree.delete(item)
                
            sorted_tickers = sorted(cache.keys())
            
            for ticker in sorted_tickers:
                data = cache[ticker]
                
                # 가격 추출 (없으면 ---)
                hl = f"{data.get('hyperliquid', {}).get('bid', '---')}"
                grvt = f"{data.get('grvt', {}).get('bid', '---')}"
                pac = f"{data.get('pacifica', {}).get('bid', '---')}"
                ext = f"{data.get('extended', {}).get('bid', '---')}"
                ltr = f"{data.get('lighter', {}).get('bid', '---')}"
                
                # 숫자 포맷팅 (소수점 정리)
                def fmt(val):
                    try: 
                        f = float(val)
                        return f"{f:.2f}" if f > 1 else f"{f:.4f}"
                    except: return "---"
                
                # 스프레드 계산
                prices = []
                for ex_data in data.values():
                    if 'bid' in ex_data: prices.append(ex_data['bid'])
                
                spread_str = "0.00%"
                status = "⚪ WAIT"
                
                if len(prices) >= 2:
                    min_p = min(prices)
                    max_p = max(prices)
                    spread = ((max_p - min_p) / min_p) * 100
                    spread_str = f"{spread:.2f}%"
                    
                    if spread > 0.5: status = "🟢 OPP"
                
                # 테이블에 삽입
                self.tree.insert("", "end", values=(
                    ticker, fmt(hl), fmt(grvt), fmt(pac), fmt(ext), fmt(ltr), spread_str, status
                ))
                
        except Exception as e:
            # GUI 갱신 중 에러는 로그에 남기지 않음 (너무 빈번할 수 있음)
            pass
            
        self.root.after(1000, self._update_market_data)

    def start_bot(self):
        if self.is_running: return
        self.is_running = True
        self.btn_start.config(state="disabled")
        self.btn_stop.config(state="normal")
        self.lbl_status.config(text="RUNNING", foreground="#00ff00")
        
        # 별도 스레드에서 봇 실행
        self.bot_thread = threading.Thread(target=self.run_bot_thread, daemon=True)
        self.bot_thread.start()

    def stop_bot(self):
        if not self.is_running: return
        self.is_running = False
        if self.bot_instance:
            # 봇 종료 시그널 (asyncio 루프에서 처리하도록 함)
            asyncio.run_coroutine_threadsafe(self.bot_instance.stop(), self.bot_loop)
            
        self.btn_start.config(state="normal")
        self.btn_stop.config(state="disabled")
        self.lbl_status.config(text="STOPPED", foreground="red")
        logging.info("🛑 봇 종료 요청됨...")

    def run_bot_thread(self):
        try:
            self.bot_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.bot_loop)
            
            self.bot_instance = ArbitrageBot(self.bot_loop)
            self.bot_loop.run_until_complete(self.bot_instance.start())
        except Exception as e:
            logging.error(f"🔥 봇 실행 중 치명적 오류: {e}")
            self.is_running = False

if __name__ == "__main__":
    root = tk.Tk()
    app = ArbitrageDashboard(root)
    root.mainloop()