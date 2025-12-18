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
    import settings  # 목표 수익률 확인용
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

# --- 메인 GUI 클래스 (V4) ---
class ArbitrageDashboardV4:
    def __init__(self, root):
        self.root = root
        self.root.title("🤖 Arbitrage Bot V4 - Live Monitor")
        self.root.geometry("1600x950") # 가로 폭을 넓혔습니다
        self.root.configure(bg="#1e1e1e")

        self.is_running = False
        self.bot_instance = None
        self.bot_loop = None
        self.log_queue = queue.Queue()
        
        self.setup_logging()
        self.setup_styles()

        # 전체 레이아웃 (좌/우 분할)
        self.create_main_layout()

        # 주기적 업데이트
        self.root.after(100, self.process_log_queue)
        self.root.after(1000, self.update_dashboard_stats)     # 1초마다 잔고/포지션 업데이트
        self.root.after(500, self.update_live_spread_monitor)  # 0.5초마다 스프레드 감시창 업데이트 (빠르게)

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        
        bg_dark = "#1e1e1e"
        bg_panel = "#252526"
        fg_white = "#ffffff"
        accent = "#007acc"

        style.configure(".", background=bg_dark, foreground=fg_white, font=("Consolas", 10))
        style.configure("TLabel", background=bg_dark, foreground=fg_white)
        style.configure("TFrame", background=bg_dark)
        style.configure("Card.TFrame", background=bg_panel, relief="flat")
        
        # 탭 스타일
        style.configure("TNotebook", background=bg_panel, borderwidth=0)
        style.configure("TNotebook.Tab", background="#333333", foreground="#aaaaaa", padding=[10, 5], font=("Arial", 10, "bold"))
        style.map("TNotebook.Tab", background=[("selected", accent)], foreground=[("selected", "white")])

        # Treeview (표) 스타일
        style.configure("Treeview", background="#2d2d2d", foreground="#e1e1e1", fieldbackground="#2d2d2d", rowheight=25, font=("Consolas", 9))
        style.configure("Treeview.Heading", background="#3e3e42", foreground="white", font=("Arial", 9, "bold"))
        style.map("Treeview", background=[("selected", "#2a2d3e")])

    def setup_logging(self):
        handler = QueueHandler(self.log_queue)
        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(logging.INFO)

    def create_main_layout(self):
        # 1. 상단 바
        self.create_top_bar()

        # 2. 메인 PanedWindow (좌: 대시보드 / 우: 실시간 감시)
        self.main_paned = tk.PanedWindow(self.root, orient="horizontal", bg="#1e1e1e", sashwidth=6, sashrelief="flat")
        self.main_paned.pack(fill="both", expand=True, padx=5, pady=5)

        # [왼쪽 패널] 기존 대시보드 (잔고, 포지션, 로그)
        self.left_panel = tk.Frame(self.main_paned, bg="#1e1e1e")
        self.main_paned.add(self.left_panel, width=1100) # 왼쪽을 더 넓게
        
        self.create_dashboard_content(self.left_panel)

        # [오른쪽 패널] 실시간 스프레드 감시창 (신규 추가)
        self.right_panel = tk.Frame(self.main_paned, bg="#252526")
        self.main_paned.add(self.right_panel, width=400)

        self.create_monitor_content(self.right_panel)

    # === [왼쪽] 기존 대시보드 내용 ===
    def create_dashboard_content(self, parent):
        # 중단 (거래소 잔고 + 활성 포지션)
        mid_paned = tk.PanedWindow(parent, orient="horizontal", bg="#1e1e1e", sashwidth=4)
        mid_paned.pack(fill="both", expand=True, pady=5)

        # 잔고 카드
        ex_frame = tk.LabelFrame(mid_paned, text=" 🏦 Exchange Balances ", bg="#1e1e1e", fg="white", font=("Arial", 11, "bold"))
        mid_paned.add(ex_frame, width=350)
        self.create_exchange_cards(ex_frame)

        # 활성 포지션
        pos_frame = tk.LabelFrame(mid_paned, text=" 📊 Active Positions (진입 중) ", bg="#1e1e1e", fg="white", font=("Arial", 11, "bold"))
        mid_paned.add(pos_frame)
        self.create_position_table(pos_frame)

        # 하단 로그
        self.create_bottom_tabs(parent)

    # === [오른쪽] 🚀 실시간 스프레드 감시창 ===
    def create_monitor_content(self, parent):
        tk.Label(parent, text="📡 Market Scanner (Top Spreads)", font=("Arial", 12, "bold"), bg="#252526", fg="#00ff99", pady=10).pack(side="top", fill="x")
        
        # 설명 레이블
        tk.Label(parent, text="현재 거래소 간 가격 차이가 큰 순서대로 나열됩니다.\n(봇은 이 데이터를 보고 진입을 노리고 있습니다)", 
                 font=("Arial", 9), bg="#252526", fg="#aaaaaa", pady=5).pack(side="top")

        # Treeview 생성
        cols = ("symbol", "spread", "route", "target")
        self.monitor_tree = ttk.Treeview(parent, columns=cols, show="headings", style="Treeview", height=30)
        
        self.monitor_tree.heading("symbol", text="티커")
        self.monitor_tree.heading("spread", text="현재 차익(%)")
        self.monitor_tree.heading("route", text="경로 (L -> S)")
        self.monitor_tree.heading("target", text="목표")

        self.monitor_tree.column("symbol", width=70, anchor="center")
        self.monitor_tree.column("spread", width=90, anchor="center") # 중요해서 넓게
        self.monitor_tree.column("route", width=120, anchor="center")
        self.monitor_tree.column("target", width=60, anchor="center")

        # 스크롤바
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=self.monitor_tree.yview)
        self.monitor_tree.configure(yscroll=scrollbar.set)
        
        self.monitor_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # 색상 태그 설정 (스프레드가 클수록 밝게)
        self.monitor_tree.tag_configure("high", foreground="#00ff00", background="#003300") # 대박 기회
        self.monitor_tree.tag_configure("mid", foreground="#ffff00") # 중박
        self.monitor_tree.tag_configure("low", foreground="#888888") # 소박

    # ... (기존 create_top_bar, create_exchange_cards, create_position_table, create_bottom_tabs 코드는 V3와 동일하므로 생략하거나 그대로 사용) ...
    # (전체 코드가 필요하면 말씀해주세요. 여기서는 핵심 로직인 업데이트 함수에 집중합니다.)

    def create_top_bar(self):
        top = tk.Frame(self.root, bg="#007acc", height=60)
        top.pack(side="top", fill="x")
        tk.Label(top, text="⚡ QUANT ARBITRAGE PRO", font=("Impact", 20), bg="#007acc", fg="white").pack(side="left", padx=20)
        
        # 버튼
        self.btn_start = tk.Button(top, text="▶ START", command=self.start_bot, bg="#2ecc71", fg="white", font=("Arial", 10, "bold"), width=10)
        self.btn_start.pack(side="left", padx=5)
        self.btn_stop = tk.Button(top, text="⏹ STOP", command=self.stop_bot, bg="#e74c3c", fg="white", font=("Arial", 10, "bold"), width=10, state="disabled")
        self.btn_stop.pack(side="left", padx=5)

        # PnL
        self.lbl_pnl = tk.Label(top, text="PnL: $0.00", font=("Arial", 14, "bold"), bg="#007acc", fg="white")
        self.lbl_pnl.pack(side="right", padx=20)

    def create_exchange_cards(self, parent):
        self.ex_widgets = {}
        exchanges = ["Hyperliquid", "GRVT", "Pacifica", "Extended", "Lighter"]
        for ex in exchanges:
            f = tk.Frame(parent, bg="#2d2d2d", pady=2)
            f.pack(fill="x", pady=2, padx=5)
            tk.Label(f, text=ex, width=10, anchor="w", bg="#2d2d2d", fg="#aaa").pack(side="left")
            l = tk.Label(f, text="$0.00", bg="#2d2d2d", fg="white", font=("Consolas", 10, "bold"))
            l.pack(side="right")
            self.ex_widgets[ex.lower()] = {"bal": l}

    def create_position_table(self, parent):
        cols = ("time", "symbol", "side", "ex", "size", "pnl")
        self.pos_tree = ttk.Treeview(parent, columns=cols, show="headings", style="Treeview")
        for c in cols: self.pos_tree.heading(c, text=c); self.pos_tree.column(c, width=80, anchor="center")
        self.pos_tree.pack(fill="both", expand=True)

    def create_bottom_tabs(self, parent):
        nb = ttk.Notebook(parent)
        nb.pack(fill="both", expand=True, pady=5)
        
        f1 = tk.Frame(nb, bg="#1e1e1e"); nb.add(f1, text="시스템 로그")
        self.log_sys = scrolledtext.ScrolledText(f1, height=8, bg="#252526", fg="#ccc", font=("Consolas", 9))
        self.log_sys.pack(fill="both", expand=True)
        
        f2 = tk.Frame(nb, bg="#1e1e1e"); nb.add(f2, text="매매 이력")
        self.log_trade = scrolledtext.ScrolledText(f2, height=8, bg="#1e1e1e", fg="#0f0", font=("Consolas", 9))
        self.log_trade.pack(fill="both", expand=True)

    # --- 🚀 [핵심 기능] 실시간 스프레드 모니터 업데이트 ---
    def update_live_spread_monitor(self):
        """봇에서 최신 시장 데이터를 가져와서 오른쪽 표를 갱신합니다."""
        if not self.bot_instance or not hasattr(self.bot_instance, 'live_market_data'):
            self.root.after(500, self.update_live_spread_monitor)
            return

        # 1. 데이터 가져오기 (Dictionary 복사)
        market_data = self.bot_instance.live_market_data.copy()
        
        if not market_data:
            self.root.after(500, self.update_live_spread_monitor)
            return

        # 2. 스프레드 높은 순으로 정렬 (내림차순)
        sorted_data = sorted(market_data.items(), key=lambda x: x[1]['spread'], reverse=True)

        # 3. 표 갱신 (기존 내용 지우고 다시 쓰기)
        # (성능 최적화를 위해 상위 30개만 표시)
        top_30 = sorted_data[:30]
        
        self.monitor_tree.delete(*self.monitor_tree.get_children())

        for ticker, data in top_30:
            spread = data['spread']
            long_ex = data['long_ex'][:3].upper() # HYP, GRV 등 3글자만
            short_ex = data['short_ex'][:3].upper()
            
            # 목표치 (예시: settings에서 가져오거나 기본값)
            # 여기서는 봇의 설정값을 알 수 없으므로 대략적인 값 표시
            target = "0.2%" 

            # 색상 태그 결정
            tag = "low"
            if spread >= 0.2: tag = "high"
            elif spread >= 0.1: tag = "mid"

            self.monitor_tree.insert("", "end", values=(
                ticker,
                f"{spread:.4f}%",
                f"{long_ex} → {short_ex}",
                target
            ), tags=(tag,))

        self.root.after(500, self.update_live_spread_monitor)

    # --- 기존 업데이트 및 제어 로직 (V3와 동일) ---
    def process_log_queue(self):
        while not self.log_queue.empty():
            l, f, r = self.log_queue.get()
            target = self.log_trade if any(k in r for k in ["진입", "청산", "주문"]) else self.log_sys
            target.insert(tk.END, f + "\n"); target.see(tk.END)
        self.root.after(100, self.process_log_queue)

    def update_dashboard_stats(self):
        if self.bot_instance and hasattr(self.bot_instance, 'virtual_portfolio'):
            vp = self.bot_instance.virtual_portfolio
            # 잔고 업데이트
            for ex, w in self.ex_widgets.items():
                bal = float(vp.balances.get(ex, 0))
                w['bal'].config(text=f"${bal:,.2f}", fg="#0f0" if bal > 100 else "#f00")
            
            # PnL 업데이트
            total_pnl = sum(t.get('pnl',0) for t in (vp.recorder.trade_log if vp.recorder else []))
            self.lbl_pnl.config(text=f"PnL: ${total_pnl:+.2f}", fg="#0f0" if total_pnl>=0 else "#f00")

            # 포지션 표 업데이트
            self.pos_tree.delete(*self.pos_tree.get_children())
            for ex, syms in vp.positions.items():
                for s, p in syms.items():
                    if p['qty'] > 0:
                        self.pos_tree.insert("", "end", values=(
                            datetime.fromtimestamp(p['entry_time']).strftime('%H:%M:%S'),
                            s, p['side'], ex, f"${p['qty']*p['price']:.1f}", "Active"
                        ))
        self.root.after(1000, self.update_dashboard_stats)

    def start_bot(self):
        if self.is_running: return
        self.is_running = True
        self.btn_start.config(state="disabled"); self.btn_stop.config(state="normal")
        self.bot_thread = threading.Thread(target=self.run_bot, daemon=True)
        self.bot_thread.start()

    def run_bot(self):
        import traceback # 트레이스백 출력을 위해 필요
        try:
            self.bot_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.bot_loop)
            
            # [수정] 봇 객체 생성 시 발생하는 에러도 잡기 위해 try 블록 안에 넣음
            self.bot_instance = ArbitrageBot(self.bot_loop)
            
            # 봇 시작
            self.bot_loop.run_until_complete(self.bot_instance.start())
            
        except Exception as e:
            # 🚨 치명적 에러 발생 시 GUI 로그에 출력
            error_msg = f"🔥 봇 시작 중 치명적 오류 발생:\n{e}\n{traceback.format_exc()}"
            logging.error(error_msg) # 큐 핸들러를 통해 GUI로 전송됨
            self.is_running = False
            
            # 버튼 상태 원복 (메인 스레드에서 실행)
            self.root.after(0, lambda: self.btn_start.config(state="normal"))
            self.root.after(0, lambda: self.btn_stop.config(state="disabled"))

    def stop_bot(self):
        if self.bot_instance: asyncio.run_coroutine_threadsafe(self.bot_instance.stop(), self.bot_loop)
        self.is_running = False
        self.btn_start.config(state="normal"); self.btn_stop.config(state="disabled")

if __name__ == "__main__":
    root = tk.Tk()
    app = ArbitrageDashboardV4(root)
    root.mainloop()