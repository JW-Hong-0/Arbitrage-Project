import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import asyncio
import logging
import queue
import threading
import sys
import time
from datetime import datetime

# [중요] V01_1 버전 봇 임포트
try:
    from arbitrage_bot_V01_1 import ArbitrageBot
    import settings  
except ImportError:
    print("❌ 'arbitrage_bot_V01_1.py' 또는 'settings.py'를 찾을 수 없습니다.")
    sys.exit(1)

# --- 불필요한 로그 필터링 ---
for lib in ["pysdk", "GrvtCcxtWS", "websockets", "urllib3", "asyncio"]:
    logging.getLogger(lib).setLevel(logging.WARNING)

class QueueHandler(logging.Handler):
    """로그를 Queue에 담아 GUI로 전달하는 핸들러"""
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue
        self.setFormatter(logging.Formatter('%(asctime)s - %(message)s', datefmt='%H:%M:%S'))

    def emit(self, record):
        try:
            msg = self.format(record)
            self.log_queue.put((record.levelno, msg))
        except Exception:
            self.handleError(record)

class ArbitrageDashboard:
    def __init__(self, root):
        self.root = root
        self.root.title("Arbitrage Bot V6 (Real Trading) - Dark Mode")
        self.root.geometry("1400x950")
        self.root.configure(bg="#1e1e1e") # 다크 배경

        # --- 스타일 설정 (Dark Theme) ---
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        colors = {
            'bg': '#1e1e1e', 
            'fg': '#ffffff', 
            'gray': '#333333', 
            'light_gray': '#4d4d4d',
            'accent': '#007acc',
            'green': '#4caf50',
            'red': '#f44336'
        }
        
        self.style.configure("TFrame", background=colors['bg'])
        self.style.configure("TLabelframe", background=colors['bg'], foreground=colors['fg'], relief="solid", borderwidth=1)
        self.style.configure("TLabelframe.Label", background=colors['bg'], foreground="#cccccc", font=("Arial", 10, "bold"))
        self.style.configure("TLabel", background=colors['bg'], foreground=colors['fg'], font=("Arial", 9))
        
        # 버튼 스타일
        self.style.configure("TButton", background="#2d2d2d", foreground=colors['fg'], borderwidth=1, font=("Arial", 9, "bold"))
        self.style.map("TButton", background=[('active', '#404040'), ('disabled', '#1a1a1a')], foreground=[('disabled', '#555555')])
        
        # 트리뷰(표) 스타일
        self.style.configure("Treeview", 
            background="#252526", 
            foreground=colors['fg'], 
            fieldbackground="#252526", 
            borderwidth=0,
            font=("Consolas", 9)
        )
        self.style.configure("Treeview.Heading", 
            background="#333333", 
            foreground=colors['fg'], 
            relief="flat",
            font=("Arial", 9, "bold")
        )
        self.style.map("Treeview.Heading", background=[('active', '#404040')])

        # 변수 초기화
        self.is_running = False
        self.bot_instance = None
        self.log_queue = queue.Queue()
        self.start_time = None

        # 로깅 핸들러 연결
        self.logger = logging.getLogger()
        self.logger.setLevel(logging.INFO)
        # 기존 핸들러 제거 (중복 방지)
        for h in self.logger.handlers[:]: self.logger.removeHandler(h)
        
        self.logger.addHandler(QueueHandler(self.log_queue))
        self.logger.addHandler(logging.StreamHandler(sys.stdout))

        # UI 구성
        self._init_ui()
        
        # 업데이트 루프 시작
        self.update_ui_loop()

    def _init_ui(self):
        # 1. 상단 영역 (컨트롤 + 요약)
        top_frame = ttk.Frame(self.root)
        top_frame.pack(side="top", fill="x", padx=10, pady=10)
        
        self._create_controls(top_frame)
        self._create_summary(top_frame)

        # 2. 거래소 상태 (Exchange Status)
        ex_frame = ttk.LabelFrame(self.root, text="Exchange Status (Real-Time)")
        ex_frame.pack(side="top", fill="x", padx=10, pady=5)
        
        cols = ("Exchange", "Total Equity", "PnL (Session)", "Active Margin")
        self.tree_ex = ttk.Treeview(ex_frame, columns=cols, show="headings", height=3)
        for c in cols: 
            self.tree_ex.heading(c, text=c)
            self.tree_ex.column(c, width=200, anchor="center")
        self.tree_ex.pack(fill="x", padx=5, pady=5)

        # 3. 중간 영역 (포지션 + 로그)
        mid_paned = ttk.PanedWindow(self.root, orient="horizontal")
        mid_paned.pack(side="top", fill="both", expand=True, padx=10, pady=5)
        
        # 좌측: 포지션
        pos_frame = ttk.LabelFrame(mid_paned, text="Active Positions")
        mid_paned.add(pos_frame, weight=3)
        
        pos_cols = ("Ticker", "Long/Short", "Entry Price", "Size", "Current Spread", "Duration", "Mode")
        self.tree_pos = ttk.Treeview(pos_frame, columns=pos_cols, show="headings", height=10)
        for c in pos_cols: 
            self.tree_pos.heading(c, text=c)
            self.tree_pos.column(c, width=100, anchor="center")
        self.tree_pos.pack(fill="both", expand=True, padx=5, pady=5)

        # 우측: 로그
        log_frame = ttk.LabelFrame(mid_paned, text="System Log")
        mid_paned.add(log_frame, weight=2)
        
        self.log_area = scrolledtext.ScrolledText(log_frame, state='disabled', height=10, 
                                                  font=("Consolas", 9), bg="#252526", fg="white", insertbackground="white")
        self.log_area.pack(fill="both", expand=True, padx=5, pady=5)
        
        # 로그 색상 태그
        self.log_area.tag_config("INFO", foreground="white")
        self.log_area.tag_config("WARNING", foreground="#FFA500") # Orange
        self.log_area.tag_config("ERROR", foreground="#FF5555")   # Red
        self.log_area.tag_config("SUCCESS", foreground="#00FF00") # Green

        # 4. 하단 영역 (마켓 워치)
        mkt_frame = ttk.LabelFrame(self.root, text="Market Watch")
        mkt_frame.pack(side="bottom", fill="x", padx=10, pady=10)
        
        mkt_cols = ("Ticker", "HL Bid", "HL Ask", "GRVT Bid", "GRVT Ask", "Spread", "Signal")
        self.tree_mkt = ttk.Treeview(mkt_frame, columns=mkt_cols, show="headings", height=6)
        for c in mkt_cols: 
            self.tree_mkt.heading(c, text=c)
            self.tree_mkt.column(c, width=120, anchor="center")
        self.tree_mkt.pack(fill="both", expand=True, padx=5, pady=5)

    def _create_controls(self, parent):
        frame = ttk.LabelFrame(parent, text="Control")
        frame.pack(side="left", fill="y", padx=5)
        
        self.btn_start = ttk.Button(frame, text="▶ START", command=self.start_bot, width=12)
        self.btn_start.pack(pady=5, padx=10)
        
        self.btn_stop = ttk.Button(frame, text="⏹ STOP", command=self.stop_bot, state="disabled", width=12)
        self.btn_stop.pack(pady=5, padx=10)
        
        self.btn_excel = ttk.Button(frame, text="💾 Excel", command=self.export_excel, width=12)
        self.btn_excel.pack(pady=5, padx=10)

        self.lbl_status = ttk.Label(frame, text="● READY", font=("Arial", 11, "bold"), foreground="gray")
        self.lbl_status.pack(pady=10)

    def _create_summary(self, parent):
        frame = ttk.LabelFrame(parent, text="Total Portfolio Summary")
        frame.pack(side="left", fill="both", expand=True, padx=5)
        
        # 요약 정보 그리드
        self.vars = {
            "Initial Equity": tk.StringVar(value="-"),
            "Current Equity": tk.StringVar(value="-"),
            "Total PnL": tk.StringVar(value="-"),
            "Run Time": tk.StringVar(value="-"),
            "Positions": tk.StringVar(value="-")
        }
        
        for i, (k, v) in enumerate(self.vars.items()):
            ttk.Label(frame, text=k, font=("Arial", 9, "bold"), foreground="#888").grid(row=0, column=i, padx=20, pady=10)
            ttk.Label(frame, textvariable=v, font=("Arial", 14, "bold"), foreground="#007acc").grid(row=1, column=i, padx=20, pady=5)

    # --- Core Logic ---

    def update_ui_loop(self):
        """GUI 갱신 루프"""
        try:
            # 1. 로그 처리
            while not self.log_queue.empty():
                lvl, msg = self.log_queue.get_nowait()
                self.log_area.config(state='normal')
                
                tag = "INFO"
                if lvl >= logging.ERROR: tag = "ERROR"
                elif lvl >= logging.WARNING: tag = "WARNING"
                elif "✅" in msg or "🚀" in msg or "💰" in msg: tag = "SUCCESS"
                
                self.log_area.insert(tk.END, msg + "\n", tag)
                self.log_area.see(tk.END)
                self.log_area.config(state='disabled')

            # 2. 데이터 갱신 (봇 실행 중일 때)
            if self.is_running and self.bot_instance:
                self._update_summary_data()
                self._update_exchange_table()
                self._update_positions_table()
                self._update_market_table()
                
        except Exception:
            pass # UI 갱신 에러는 무시하고 계속 진행
            
        self.root.after(100, self.update_ui_loop)

    def _update_summary_data(self):
        init = self.bot_instance.initial_equity
        curr = self.bot_instance.current_equity
        pnl = self.bot_instance.total_pnl
        
        # 시간 계산
        runtime = int(time.time() - self.start_time)
        h, r = divmod(runtime, 3600)
        m, s = divmod(r, 60)
        
        # 포지션 수
        if self.bot_instance.real_trading:
            cnt = len(self.bot_instance.real_positions)
        else:
            cnt = len(self.bot_instance.virtual_portfolio.get_active_tickers())

        self.vars["Initial Equity"].set(f"${init:,.2f}")
        self.vars["Current Equity"].set(f"${curr:,.2f}")
        
        pnl_pct = (pnl / init * 100) if init > 0 else 0.0
        self.vars["Total PnL"].set(f"${pnl:,.2f} ({pnl_pct:+.2f}%)")
        
        self.vars["Run Time"].set(f"{h:02}:{m:02}:{s:02}")
        self.vars["Positions"].set(str(cnt))

    def _update_exchange_table(self):
        # 전체 삭제 후 다시 그리기 (데이터량이 적음)
        for item in self.tree_ex.get_children(): self.tree_ex.delete(item)
        
        # 실전 매매: 실제 잔고 사용
        if self.bot_instance.real_trading:
            for ex, bal in self.bot_instance.exchange_balances.items():
                init = self.bot_instance.initial_exchange_balances.get(ex, bal)
                pnl = bal - init
                
                # 활성 포지션 금액(Notional) 계산
                active_notional = 0.0
                for p in self.bot_instance.real_positions.values():
                    if p.get('long_ex') == ex or p.get('short_ex') == ex:
                        active_notional += (p['entry_price'] * p['qty'])
                        
                self.tree_ex.insert("", "end", values=(ex, f"${bal:,.2f}", f"${pnl:+.2f}", f"${active_notional:,.2f}"))
        
        # 가상 매매: 가상 잔고 사용
        else:
            balances = self.bot_instance.virtual_portfolio.balances
            for ex, bal in balances.items():
                if ex in self.bot_instance.active_exchanges:
                    self.tree_ex.insert("", "end", values=(ex, f"${bal:,.2f}", "-", "Virtual"))

    def _update_positions_table(self):
        for item in self.tree_pos.get_children(): self.tree_pos.delete(item)
        
        # 실전 포지션
        if self.bot_instance.real_trading:
            for t, p in self.bot_instance.real_positions.items():
                dur = int(time.time() - p['entry_time'])
                self.tree_pos.insert("", "end", values=(
                    t, f"{p['long_ex']}/{p['short_ex']}", 
                    f"${p['entry_price']:,.2f}", f"{p['qty']:.5f}", 
                    "-", f"{dur}s", "REAL"
                ))
        # 가상 포트폴리오
        else:
            tickers = self.bot_instance.virtual_portfolio.get_active_tickers()
            for t in tickers:
                p = self.bot_instance.virtual_portfolio.get_active_position(t)
                if p:
                    entry_time = p['long']['data'].get('entry_time', time.time())
                    dur = int(time.time() - entry_time)
                    self.tree_pos.insert("", "end", values=(
                        t, f"{p['long']['ex']}/{p['short']['ex']}",
                        f"${p['long']['data']['price']:,.2f}",
                        f"{p['long']['data']['qty']:.5f}",
                        "-", f"{dur}s", "VIRTUAL"
                    ))

    def _update_market_table(self):
        # 기존 아이템 ID 매핑 (깜빡임 방지용 업데이트)
        existing = {self.tree_mkt.item(i)['values'][0]: i for i in self.tree_mkt.get_children()}
        
        cache = self.bot_instance.market_cache
        for ticker, ex_data in cache.items():
            hl = ex_data.get('hyperliquid', {})
            grvt = ex_data.get('grvt', {})
            
            hl_bid = f"${hl.get('bid', 0):,.2f}" if hl else "-"
            hl_ask = f"${hl.get('ask', 0):,.2f}" if hl else "-"
            grvt_bid = f"${grvt.get('bid', 0):,.2f}" if grvt else "-"
            grvt_ask = f"${grvt.get('ask', 0):,.2f}" if grvt else "-"
            
            spread_str = "-"
            signal = ""
            
            # Spread (HL Long 관점: GRVT Bid - HL Ask)
            if hl and grvt and hl.get('ask') and grvt.get('bid'):
                h_ask = hl['ask']
                g_bid = grvt['bid']
                if h_ask > 0:
                    spread = (g_bid - h_ask) / h_ask * 100
                    spread_str = f"{spread:+.2f}%"
                    if spread > 0.5: signal = "🟢 BUY" # 단순 예시
            
            values = (ticker, hl_bid, hl_ask, grvt_bid, grvt_ask, spread_str, signal)
            
            if ticker in existing:
                self.tree_mkt.item(existing[ticker], values=values)
            else:
                self.tree_mkt.insert("", "end", values=values)

    # --- Bot Controls ---
    def start_bot(self):
        if self.is_running: return
        self.is_running = True
        self.start_time = time.time()
        
        self.btn_start.config(state="disabled")
        self.btn_stop.config(state="normal")
        self.lbl_status.config(text="● RUNNING", foreground="#00ff00") # Green
        
        self.bot_thread = threading.Thread(target=self._run_bot_process, daemon=True)
        self.bot_thread.start()

    def _run_bot_process(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self.bot_instance = ArbitrageBot(loop=loop)
        loop.run_until_complete(self.bot_instance.start())

    def stop_bot(self):
        if not self.is_running: return
        self.is_running = False
        
        if self.bot_instance:
            asyncio.run(self.bot_instance.stop())
            
        self.btn_start.config(state="normal")
        self.btn_stop.config(state="disabled")
        self.lbl_status.config(text="● STOPPED", foreground="#ff5555") # Red

    def export_excel(self):
        if self.bot_instance:
            self.bot_instance.save_excel()
            messagebox.showinfo("Export", "엑셀 저장 완료")
        else:
            messagebox.showwarning("Error", "봇이 초기화되지 않음")

if __name__ == "__main__":
    root = tk.Tk()
    app = ArbitrageDashboard(root)
    root.mainloop()