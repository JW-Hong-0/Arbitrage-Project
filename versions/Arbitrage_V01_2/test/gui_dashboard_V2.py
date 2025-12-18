import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import asyncio
import logging
import queue
import threading
import sys
import time
from decimal import Decimal

# 기존 봇 모듈 임포트
try:
    from arbitrage_bot import ArbitrageBot
except ImportError:
    print("❌ 'arbitrage_bot.py' 파일을 찾을 수 없습니다.")
    sys.exit(1)

# --- 로그 큐 핸들러 ---
class QueueHandler(logging.Handler):
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue
        self.setFormatter(logging.Formatter('%(asctime)s - %(message)s', datefmt='%H:%M:%S'))

    def emit(self, record):
        self.log_queue.put(record)

# --- 메인 GUI 클래스 ---
class ArbitrageDashboardV2:
    def __init__(self, root):
        self.root = root
        self.root.title("🤖 Arbitrage Bot Control Tower V2")
        self.root.geometry("1400x900")
        self.root.configure(bg="#1e1e1e")  # 다크 모드 배경

        # 데이터 변수
        self.is_running = False
        self.bot_instance = None
        self.log_queue = queue.Queue()
        self.setup_logging()

        # 스타일 설정
        self.setup_styles()

        # UI 레이아웃 구성
        self.create_top_summary_bar()
        self.create_main_split_view()
        self.create_bottom_log_view()

        # 업데이트 루프 시작
        self.root.after(100, self.process_log_queue)
        self.root.after(1000, self.update_dashboard_stats)

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        
        # 다크 테마 색상 정의
        bg_color = "#1e1e1e"
        fg_color = "#ffffff"
        accent_color = "#007acc"
        panel_bg = "#2d2d2d"

        # 기본 스타일
        style.configure(".", background=bg_color, foreground=fg_color, font=("Consolas", 10))
        style.configure("TLabel", background=bg_color, foreground=fg_color)
        style.configure("TButton", background=accent_color, foreground="white", padding=6)
        style.map("TButton", background=[("active", "#005f9e")])

        # 카드 프레임 스타일
        style.configure("Card.TFrame", background=panel_bg, relief="flat")
        style.configure("CardTitle.TLabel", background=panel_bg, foreground="#aaaaaa", font=("Arial", 10, "bold"))
        style.configure("CardValue.TLabel", background=panel_bg, foreground="#ffffff", font=("Arial", 16, "bold"))
        
        # Treeview (표) 스타일
        style.configure("Treeview", 
                        background="#252526", 
                        foreground="#cccccc", 
                        fieldbackground="#252526",
                        rowheight=30,
                        font=("Consolas", 10))
        style.configure("Treeview.Heading", 
                        background="#333333", 
                        foreground="#ffffff", 
                        font=("Arial", 10, "bold"),
                        relief="flat")
        style.map("Treeview", background=[("selected", accent_color)])

    def setup_logging(self):
        handler = QueueHandler(self.log_queue)
        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(logging.INFO)

    # === 1. 상단 요약 바 (Top Summary) ===
    def create_top_summary_bar(self):
        top_frame = tk.Frame(self.root, bg="#007acc", height=80)
        top_frame.pack(side="top", fill="x")
        
        # 타이틀
        tk.Label(top_frame, text="⚡ QUANT ARBITRAGE BOT", font=("Impact", 24), bg="#007acc", fg="white").pack(side="left", padx=20)

        # 요약 정보 컨테이너
        stats_frame = tk.Frame(top_frame, bg="#007acc")
        stats_frame.pack(side="right", padx=20)

        # 요약 지표 생성 함수
        def create_stat(parent, label, value_id):
            f = tk.Frame(parent, bg="#007acc", padx=15)
            f.pack(side="left")
            tk.Label(f, text=label, font=("Arial", 10), bg="#007acc", fg="#e1e1e1").pack(anchor="w")
            lbl = tk.Label(f, text="0", font=("Arial", 20, "bold"), bg="#007acc", fg="white")
            lbl.pack(anchor="w")
            setattr(self, value_id, lbl) # self.lbl_total_pnl 등으로 저장

        create_stat(stats_frame, "총 실현 수익 (Total PnL)", "lbl_total_pnl")
        create_stat(stats_frame, "총 수수료 (Total Fees)", "lbl_total_fees")
        create_stat(stats_frame, "총 거래 횟수 (Trades)", "lbl_total_trades")

        # 제어 버튼
        btn_frame = tk.Frame(top_frame, bg="#007acc")
        btn_frame.pack(side="left", padx=50)
        
        self.btn_start = tk.Button(btn_frame, text="▶ START BOT", command=self.start_bot, 
                                   bg="#2ecc71", fg="white", font=("Arial", 12, "bold"), width=12, relief="flat")
        self.btn_start.pack(side="left", padx=5)

        self.btn_stop = tk.Button(btn_frame, text="⏹ STOP", command=self.stop_bot, 
                                  bg="#e74c3c", fg="white", font=("Arial", 12, "bold"), width=12, relief="flat", state="disabled")
        self.btn_stop.pack(side="left", padx=5)

    # === 2. 메인 분할 화면 (Left: Exchanges, Right: Positions) ===
    def create_main_split_view(self):
        main_paned = tk.PanedWindow(self.root, orient="horizontal", bg="#1e1e1e", sashwidth=4, sashrelief="flat")
        main_paned.pack(fill="both", expand=True, padx=10, pady=10)

        # [좌측] 거래소 카드 영역
        left_frame = tk.Frame(main_paned, bg="#1e1e1e")
        main_paned.add(left_frame, width=500)
        
        tk.Label(left_frame, text="🏦 거래소별 자산 현황 (Exchange Balances)", font=("Arial", 14, "bold"), bg="#1e1e1e", fg="white").pack(anchor="w", pady=(0, 10))
        
        self.exchange_container = tk.Frame(left_frame, bg="#1e1e1e")
        self.exchange_container.pack(fill="both", expand=True)

        # 거래소 목록
        self.exchanges = ["Hyperliquid", "GRVT", "Pacifica", "Extended", "Lighter"]
        self.ex_widgets = {}

        # 그리드 형태로 카드 배치 (2열)
        for idx, ex_name in enumerate(self.exchanges):
            row = idx // 2
            col = idx % 2
            self.create_exchange_card(self.exchange_container, ex_name, row, col)

        # [우측] 포지션 테이블 영역
        right_frame = tk.Frame(main_paned, bg="#1e1e1e")
        main_paned.add(right_frame)

        tk.Label(right_frame, text="📊 활성 포지션 (Active Positions)", font=("Arial", 14, "bold"), bg="#1e1e1e", fg="white").pack(anchor="w", pady=(0, 10))

        # Treeview
        columns = ("symbol", "long", "short", "entry_gap", "size", "pnl", "time")
        self.tree = ttk.Treeview(right_frame, columns=columns, show="headings", style="Treeview")
        
        # 헤더 설정
        headers = {
            "symbol": "코인", "long": "Long (매수)", "short": "Short (매도)", 
            "entry_gap": "진입 차이", "size": "규모($)", "pnl": "예상 PnL", "time": "경과 시간"
        }
        for col, text in headers.items():
            self.tree.heading(col, text=text)
            self.tree.column(col, anchor="center", width=100)

        self.tree.pack(fill="both", expand=True)

    def create_exchange_card(self, parent, name, row, col):
        card = ttk.Frame(parent, style="Card.TFrame", padding=15)
        card.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
        parent.grid_columnconfigure(col, weight=1)

        # 카드 내부 내용
        ttk.Label(card, text=name, style="CardTitle.TLabel").pack(anchor="w")
        
        # 잔고 표시
        lbl_bal = ttk.Label(card, text="$0.00", style="CardValue.TLabel")
        lbl_bal.pack(anchor="w", pady=5)
        
        # 세부 정보 (매매 횟수 등) - 작은 글씨
        lbl_detail = ttk.Label(card, text="Trades: 0 | PnL: $0.00", background="#2d2d2d", foreground="#888888", font=("Arial", 8))
        lbl_detail.pack(anchor="w")

        self.ex_widgets[name] = {"bal": lbl_bal, "detail": lbl_detail, "frame": card}

    # === 3. 하단 로그 창 (Bottom Log) ===
    def create_bottom_log_view(self):
        log_frame = tk.LabelFrame(self.root, text="📜 시스템 로그", bg="#1e1e1e", fg="#aaaaaa", height=200)
        log_frame.pack(side="bottom", fill="x", padx=10, pady=5)

        self.log_area = scrolledtext.ScrolledText(log_frame, height=8, state='disabled', 
                                                  bg="#252526", fg="#d4d4d4", font=("Consolas", 9), insertbackground="white")
        self.log_area.pack(fill="both", expand=True)

    # --- 기능 로직 ---

    def process_log_queue(self):
        while not self.log_queue.empty():
            record = self.log_queue.get()
            msg = self.format_log_record(record)
            self.log_area.configure(state='normal')
            self.log_area.insert(tk.END, msg + "\n")
            self.log_area.see(tk.END)
            self.log_area.configure(state='disabled')
        self.root.after(100, self.process_log_queue)

    def format_log_record(self, record):
        # 로그 레벨에 따라 색상이나 아이콘 추가 가능 (여기서는 단순 텍스트)
        return f"[{record.asctime}] {record.message}"

    def update_dashboard_stats(self):
        """1초마다 봇의 데이터를 읽어와서 UI 갱신"""
        if self.bot_instance and hasattr(self.bot_instance, 'virtual_portfolio'):
            vp = self.bot_instance.virtual_portfolio
            
            # 1. 상단 요약 바 갱신
            # (PortfolioManager의 trade_log 리스트를 순회하며 계산)
            trade_log = []
            if hasattr(vp, 'recorder') and vp.recorder:
                trade_log = vp.recorder.trade_log

            total_trades = len(trade_log)
            total_fees = sum(float(t.get('fee', 0)) for t in trade_log)
            total_pnl = sum(float(t.get('pnl', 0)) for t in trade_log)

            self.lbl_total_trades.config(text=f"{total_trades}회")
            self.lbl_total_fees.config(text=f"${total_fees:.2f}")
            
            pnl_color = "#2ecc71" if total_pnl >= 0 else "#e74c3c"
            self.lbl_total_pnl.config(text=f"${total_pnl:.2f}", fg=pnl_color)

            # 2. 거래소 카드 갱신
            for ex_name, widgets in self.ex_widgets.items():
                # 잔고 가져오기 (키 이름 소문자 변환 주의)
                key = ex_name.lower()
                bal = float(vp.balances.get(key, 0.0))
                
                widgets['bal'].config(text=f"${bal:,.2f}")
                
                # 잔고 부족 경고 (예: $50 미만 시 빨간색 배경)
                if bal < 50:
                    widgets['frame'].configure(style="Error.TFrame") # 스타일 정의 필요하지만 여기선 생략하고 텍스트 색 변경
                    widgets['bal'].configure(foreground="#ff5555")
                else:
                    widgets['bal'].configure(foreground="#ffffff")

                # (추가) 해당 거래소 관련 거래 통계 계산
                # 로그에서 해당 거래소가 포함된 거래 찾기 (long_ex 또는 short_ex)
                ex_trades = [t for t in trade_log if t.get('long_ex') == key or t.get('short_ex') == key]
                ex_count = len(ex_trades)
                ex_pnl = sum(float(t.get('pnl', 0)) for t in ex_trades if t.get('long_ex') == key) # PnL 귀속은 대략적으로

                # 여기서는 공간상 간단히 표기
                # widgets['detail'].config(text=f"Trades: {ex_count}") 

            # 3. 포지션 테이블 갱신
            self.update_position_table(vp.positions)

        self.root.after(1000, self.update_dashboard_stats)

    def update_position_table(self, positions_data):
        # 기존 항목 삭제
        for item in self.tree.get_children():
            self.tree.delete(item)

        # positions_data 구조: { 'pair_key': {'BTC': {'qty':...}, 'ETH':...} }
        # 실제 구조에 맞춰 파싱 필요 (virtual_portfolio_manager.py 참고)
        # 예시: positions['hyperliquid_grvt']['BTC'] = { ... }
        
        for pair_key, symbols in positions_data.items():
            ex_parts = pair_key.split('_') # hyperliquid_grvt
            long_ex_name = ex_parts[0]
            short_ex_name = ex_parts[1] if len(ex_parts) > 1 else "?"

            for symbol, pos in symbols.items():
                if pos.get('qty', 0) > 0:
                    entry_time = pos.get('entry_time', 0)
                    elapsed = int(time.time() - entry_time) if entry_time > 0 else 0
                    
                    # 수수료/슬리피지 고려한 대략적 현재 PnL (구현 필요, 여기선 0)
                    est_pnl = 0.0 

                    self.tree.insert("", "end", values=(
                        symbol,
                        long_ex_name.title(),
                        short_ex_name.title(),
                        f"{pos.get('spread', 0):.2f}%",
                        f"${pos.get('qty', 0) * pos.get('price', 0):.1f}",
                        f"${est_pnl:.2f}",
                        f"{elapsed}s"
                    ))

    # --- 봇 제어 ---
    def start_bot(self):
        if self.is_running: return
        self.is_running = True
        self.btn_start.config(state="disabled", bg="#555555")
        self.btn_stop.config(state="normal", bg="#e74c3c")
        
        self.log_area.configure(state='normal')
        self.log_area.insert(tk.END, "🚀 봇 시스템을 시작합니다...\n")
        self.log_area.configure(state='disabled')

        # 별도 스레드에서 비동기 봇 실행
        self.bot_thread = threading.Thread(target=self.run_async_bot, daemon=True)
        self.bot_thread.start()

    def run_async_bot(self):
        try:
            self.bot_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.bot_loop)
            self.bot_instance = ArbitrageBot(self.bot_loop) # 인자 전달 확인
            self.bot_loop.run_until_complete(self.bot_instance.start())
        except Exception as e:
            logging.error(f"봇 실행 중 오류: {e}")
        finally:
            self.is_running = False

    def stop_bot(self):
        if not self.is_running: return
        logging.info("🛑 봇 종료 요청 중...")
        self.btn_stop.config(text="종료 중...", state="disabled")
        
        if self.bot_instance:
            asyncio.run_coroutine_threadsafe(self.bot_instance.stop(), self.bot_loop)
        
        self.root.after(2000, lambda: self.btn_start.config(state="normal", bg="#2ecc71"))
        self.root.after(2000, lambda: self.btn_stop.config(text="⏹ STOP", state="disabled"))
        self.is_running = False

# --- 실행 진입점 ---
if __name__ == "__main__":
    root = tk.Tk()
    app = ArbitrageDashboardV2(root)
    root.mainloop()