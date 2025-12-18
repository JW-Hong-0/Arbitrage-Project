import tkinter as tk
from tkinter import ttk, scrolledtext, font
import asyncio
import logging
import queue
import threading
import sys
import time

# 기존 봇 모듈 임포트
try:
    from arbitrage_bot import ArbitrageBot
    import settings  
except ImportError:
    print("❌ 'arbitrage_bot.py' 또는 'settings.py'를 찾을 수 없습니다.")
    sys.exit(1)

# --- 로그 설정 ---
logging.getLogger("pysdk").setLevel(logging.WARNING)
logging.getLogger("GrvtCcxtWS").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("websockets").setLevel(logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.WARNING)

# 큐 핸들러 (로그를 GUI로 전송)
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

class ArbitrageBot:
    def __init__(self, loop=None): # loop 인자 추가
        self.loop = loop if loop else asyncio.get_event_loop()
        
        self.root = root
        self.root.title("🚀 5-Exchange Arbitrage Commander V4")
        self.root.geometry("1600x950")
        self.root.configure(bg="#1e1e1e") # 다크 모드 배경

        # 스타일 설정
        self._setup_styles()

        # 변수
        self.is_running = False
        self.log_queue = queue.Queue()
        self.bot_loop = None
        self.bot_instance = None
        self.tree_items = {} # 트리뷰 아이템 캐시 (깜빡임 방지용)
        
        # UI 구성
        self._create_layout()
        
        # 로그 핸들러 연결
        queue_handler = QueueHandler(self.log_queue)
        logging.getLogger().addHandler(queue_handler)
        
        # 루프 시작
        self.root.after(100, self._process_logs)
        self.root.after(1000, self._update_market_data)

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        
        # 메인 컬러 테마
        bg_dark = "#1e1e1e"
        fg_white = "#ffffff"
        accent_color = "#007acc"
        
        style.configure(".", background=bg_dark, foreground=fg_white)
        style.configure("TFrame", background=bg_dark)
        style.configure("TLabel", background=bg_dark, foreground=fg_white, font=('Segoe UI', 10))
        style.configure("Header.TLabel", font=('Segoe UI', 12, 'bold'), foreground="#4cc2ff")
        
        # 버튼 스타일
        style.configure("TButton", padding=6, relief="flat", background="#333333", foreground="white")
        style.map("TButton", background=[('active', accent_color)])
        
        # 트리뷰 스타일 (표)
        style.configure("Treeview", 
            background="#252526", 
            fieldbackground="#252526", 
            foreground="#cccccc", 
            rowheight=30,
            font=('Consolas', 10)
        )
        style.configure("Treeview.Heading", 
            background="#333333", 
            foreground="white", 
            font=('Segoe UI', 10, 'bold'),
            relief="flat"
        )
        style.map("Treeview", background=[('selected', accent_color)])

    def _create_layout(self):
        # 1. 상단 헤더 (봇 제어)
        header_frame = ttk.Frame(self.root, padding="10")
        header_frame.pack(fill=tk.X)
        
        ttk.Label(header_frame, text="🤖 ARBITRAGE BOT CONTROL", style="Header.TLabel").pack(side=tk.LEFT, padx=10)
        
        self.btn_start = ttk.Button(header_frame, text="▶ START ENGINE", command=self.start_bot)
        self.btn_start.pack(side=tk.LEFT, padx=5)
        
        self.btn_stop = ttk.Button(header_frame, text="⏹ EMERGENCY STOP", command=self.stop_bot, state="disabled")
        self.btn_stop.pack(side=tk.LEFT, padx=5)
        
        self.lbl_status = ttk.Label(header_frame, text="● STOPPED", foreground="#ff5555", font=('Segoe UI', 10, 'bold'))
        self.lbl_status.pack(side=tk.LEFT, padx=20)

        # 2. 베스트 기회 포착 (Highlight Section)
        self.opp_frame = tk.Frame(self.root, bg="#2d2d30", bd=2, relief="ridge")
        self.opp_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Label(self.opp_frame, text="⚡ TOP OPPORTUNITY", bg="#2d2d30", fg="#ffd700", font=('Segoe UI', 11, 'bold')).pack(pady=5)
        
        # 기회 정보 표시 라벨 (동적 갱신)
        self.lbl_best_opp = tk.Label(self.opp_frame, 
            text="Waiting for market data...", 
            bg="#2d2d30", fg="white", 
            font=('Segoe UI', 16, 'bold')
        )
        self.lbl_best_opp.pack(pady=10)
        
        self.lbl_best_detail = tk.Label(self.opp_frame, 
            text="-", 
            bg="#2d2d30", fg="#aaaaaa", 
            font=('Segoe UI', 11)
        )
        self.lbl_best_detail.pack(pady=(0, 10))

        # 3. 메인 컨텐츠 (좌우 분할)
        paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # [왼쪽] 전체 시세 테이블
        table_frame = ttk.LabelFrame(paned, text="📊 Real-time Market Watch", padding=5)
        paned.add(table_frame, weight=3)
        
        cols = ("Ticker", "HL", "GRVT", "PAC", "EXT", "LTR", "Spread", "Status")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings", selectmode="browse")
        
        # 컬럼 설정
        widths = [90, 90, 90, 90, 90, 90, 90, 100]
        for col, w in zip(cols, widths):
            self.tree.heading(col, text=col, anchor="center")
            self.tree.column(col, width=w, anchor="center")
        
        # 스크롤바
        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 태그 설정 (색상)
        self.tree.tag_configure("opp", background="#1e3a29", foreground="#55ff55") # 기회 (초록 배경)
        self.tree.tag_configure("wait", background="#252526", foreground="#aaaaaa") # 대기 (기본)

        # [오른쪽] 로그 및 포트폴리오
        right_panel = ttk.Frame(paned)
        paned.add(right_panel, weight=1)
        
        # 로그창
        log_frame = ttk.LabelFrame(right_panel, text="📜 System Logs", padding=5)
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        self.log_area = scrolledtext.ScrolledText(log_frame, height=15, bg="#111", fg="#0f0", font=('Consolas', 9), state='disabled')
        self.log_area.pack(fill=tk.BOTH, expand=True)
        
        # 로그 태그 색상
        self.log_area.tag_config("INFO", foreground="#cccccc")
        self.log_area.tag_config("WARN", foreground="orange")
        self.log_area.tag_config("ERROR", foreground="#ff5555")
        self.log_area.tag_config("TRADE", foreground="#00ff00", font=('Consolas', 9, 'bold'))

    def _process_logs(self):
        """큐에 쌓인 로그를 화면에 출력"""
        while not self.log_queue.empty():
            level, msg, raw_msg = self.log_queue.get()
            self.log_area.config(state='normal')
            
            tag = "INFO"
            if level >= logging.ERROR: tag = "ERROR"
            elif level >= logging.WARNING: tag = "WARN"
            if "체결" in raw_msg or "기회" in raw_msg: tag = "TRADE"
            
            self.log_area.insert(tk.END, msg + "\n", tag)
            self.log_area.see(tk.END)
            self.log_area.config(state='disabled')
            
        self.root.after(100, self._process_logs)

    def _update_market_data(self):
        """
        [핵심] 봇 데이터 가져오기 및 화면 갱신 (Flicker-Free)
        """
        if not self.bot_instance or not self.is_running:
            self.root.after(1000, self._update_market_data)
            return

        try:
            # 봇의 데이터 캐시 읽기
            cache = self.bot_instance.market_cache
            sorted_tickers = sorted(cache.keys())
            
            best_spread = -999
            best_info = None

            for ticker in sorted_tickers:
                data = cache[ticker]
                
                # 가격 포맷팅 함수
                def get_p(ex):
                    val = data.get(ex, {}).get('bid', 0)
                    if val == 0: return "---"
                    return f"{val:.4f}" if val < 10 else f"{val:.2f}"
                
                hl, grvt, pac, ext, ltr = get_p('hyperliquid'), get_p('grvt'), get_p('pacifica'), get_p('extended'), get_p('lighter')
                
                # 스프레드 계산
                prices = []
                price_map = {}
                for ex in ['hyperliquid', 'grvt', 'pacifica', 'extended', 'lighter']:
                    p = data.get(ex, {}).get('bid', 0)
                    if p > 0: 
                        prices.append(p)
                        price_map[ex] = p
                
                spread_val = 0.0
                spread_str = "0.00%"
                status = "WAIT"
                tag = "wait"
                
                if len(prices) >= 2:
                    min_p = min(prices)
                    max_p = max(prices)
                    spread_val = ((max_p - min_p) / min_p) * 100
                    spread_str = f"{spread_val:.2f}%"
                    
                    if spread_val > 0.5:
                        status = "🟢 OPP"
                        tag = "opp"
                        
                        # 최고 기회 갱신
                        if spread_val > best_spread:
                            best_spread = spread_val
                            # 최저가 매수처 / 최고가 매도처 찾기
                            # 주의: 실제 매매는 Ask로 사고 Bid로 팔아야 하지만, 모니터링은 Bid 기준으로 단순 비교
                            min_ex = min(price_map, key=price_map.get)
                            max_ex = max(price_map, key=price_map.get)
                            best_info = (ticker, spread_val, min_ex, min_p, max_ex, max_p)

                # --- 트리뷰 업데이트 (Flicker-Free 방식) ---
                values = (ticker, hl, grvt, pac, ext, ltr, spread_str, status)
                
                if ticker in self.tree_items:
                    # 이미 있으면 값만 업데이트
                    item_id = self.tree_items[ticker]
                    self.tree.item(item_id, values=values, tags=(tag,))
                else:
                    # 없으면 새로 추가
                    item_id = self.tree.insert("", "end", values=values, tags=(tag,))
                    self.tree_items[ticker] = item_id
            
            # 상단 Best Opportunity 업데이트
            if best_info:
                t, s, buy_ex, buy_p, sell_ex, sell_p = best_info
                self.lbl_best_opp.config(text=f"🔥 Best: {t}  [{s:.2f}%]", fg="#00ff00")
                self.lbl_best_detail.config(text=f"Buy: {buy_ex.upper()} (${buy_p})  ➡  Sell: {sell_ex.upper()} (${sell_p})")
                self.opp_frame.config(bg="#1e3a29") # 초록 배경 강조
            else:
                self.lbl_best_opp.config(text="Scanning for opportunities...", fg="white")
                self.lbl_best_detail.config(text="-")
                self.opp_frame.config(bg="#2d2d30") # 기본 배경

        except Exception as e:
            # logging.error(f"GUI Update Error: {e}") # 디버깅 시 주석 해제
            pass
            
        self.root.after(1000, self._update_market_data)

    def start_bot(self):
        if self.is_running: return
        self.is_running = True
        self.btn_start.config(state="disabled")
        self.btn_stop.config(state="normal")
        self.lbl_status.config(text="● RUNNING", foreground="#00ff00")
        
        # 봇 스레드 시작
        self.bot_thread = threading.Thread(target=self.run_bot, daemon=True)
        self.bot_thread.start()

    def stop_bot(self):
        if not self.is_running: return
        self.is_running = False
        if self.bot_instance and self.bot_loop:
            asyncio.run_coroutine_threadsafe(self.bot_instance.stop(), self.bot_loop)
            
        self.btn_start.config(state="normal")
        self.btn_stop.config(state="disabled")
        self.lbl_status.config(text="● STOPPED", foreground="#ff5555")
        logging.info("🛑 봇 종료 중...")

    def run_bot(self):
        try:
            self.bot_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.bot_loop)
            self.bot_instance = ArbitrageBot(self.bot_loop)
            self.bot_loop.run_until_complete(self.bot_instance.start())
        except Exception as e:
            logging.error(f"🔥 Bot Crash: {e}")
            self.is_running = False

if __name__ == "__main__":
    root = tk.Tk()
    app = ArbitrageDashboard(root)
    root.mainloop()