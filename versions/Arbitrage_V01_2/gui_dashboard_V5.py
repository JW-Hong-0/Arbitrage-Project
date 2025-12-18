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
        self.root.title("🚀 Arbitrage Commander V8 (Margin & Equity View)")
        self.root.geometry("1600x1000")
        self.root.configure(bg="#1e1e1e")

        self._setup_styles()

        self.is_running = False
        self.log_queue = queue.Queue()
        self.bot_loop = None
        self.bot_instance = None
        self.tree_items = {} 
        
        self._create_layout()
        
        queue_handler = QueueHandler(self.log_queue)
        logging.getLogger().addHandler(queue_handler)
        
        self.root.after(100, self._process_logs)
        self.root.after(1000, self._update_ui)

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        
        bg_dark = "#1e1e1e"
        fg_white = "#ffffff"
        accent_color = "#007acc"
        
        style.configure(".", background=bg_dark, foreground=fg_white)
        style.configure("TFrame", background=bg_dark)
        style.configure("TLabel", background=bg_dark, foreground=fg_white, font=('Segoe UI', 10))
        
        style.configure("Card.TFrame", background="#252526", relief="flat")
        style.configure("TButton", padding=6, relief="flat", background="#333333", foreground="white")
        style.map("TButton", background=[('active', accent_color)])
        
        style.configure("Treeview", background="#252526", fieldbackground="#252526", foreground="#cccccc", rowheight=25, font=('Consolas', 9))
        style.configure("Treeview.Heading", background="#333333", foreground="white", font=('Segoe UI', 9, 'bold'), relief="flat")
        style.map("Treeview", background=[('selected', accent_color)])

    def _create_layout(self):
        # === 1. 상단 요약 ===
        summary_frame = ttk.Frame(self.root, style="Card.TFrame", padding=10)
        summary_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ctrl_frame = ttk.Frame(summary_frame, style="Card.TFrame")
        ctrl_frame.pack(side=tk.LEFT)
        
        self.btn_start = ttk.Button(ctrl_frame, text="▶ START", command=self.start_bot)
        self.btn_start.pack(side=tk.LEFT, padx=5)
        self.btn_stop = ttk.Button(ctrl_frame, text="⏹ STOP", command=self.stop_bot, state="disabled")
        self.btn_stop.pack(side=tk.LEFT, padx=5)
        self.btn_excel = ttk.Button(ctrl_frame, text="💾 Excel", command=self.export_excel)
        self.btn_excel.pack(side=tk.LEFT, padx=5)
        
        self.lbl_status = ttk.Label(ctrl_frame, text="● STOPPED", foreground="#ff5555", font=('Segoe UI', 10, 'bold'), background="#252526")
        self.lbl_status.pack(side=tk.LEFT, padx=15)
        
        stats_frame = ttk.Frame(summary_frame, style="Card.TFrame")
        stats_frame.pack(side=tk.RIGHT)
        
        self.lbl_total_bal = ttk.Label(stats_frame, text="Total Equity: $1000.00", font=('Segoe UI', 14, 'bold'), background="#252526", foreground="#00ff00")
        self.lbl_total_bal.pack(side=tk.LEFT, padx=15)
        
        self.lbl_total_pnl = ttk.Label(stats_frame, text="PnL: $0.00 (0.00%)", font=('Segoe UI', 12), background="#252526", foreground="white")
        self.lbl_total_pnl.pack(side=tk.LEFT, padx=15)
        
        self.lbl_total_trades = ttk.Label(stats_frame, text="Trades: 0", font=('Segoe UI', 12), background="#252526", foreground="#aaaaaa")
        self.lbl_total_trades.pack(side=tk.LEFT, padx=15)

        # === 2. 거래소별 현황 (Used Margin 추가) ===
        ex_frame = ttk.LabelFrame(self.root, text="🏦 Exchange Status (Equity / PnL / Used Margin)", padding=5)
        ex_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.ex_labels = {}
        exchanges = ['Hyperliquid', 'GRVT', 'Pacifica', 'Extended', 'Lighter']
        
        for ex in exchanges:
            f = ttk.Frame(ex_frame, padding=5, style="Card.TFrame")
            f.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
            
            ttk.Label(f, text=ex, font=('Segoe UI', 10, 'bold'), foreground="#4cc2ff", background="#252526").pack()
            bal = ttk.Label(f, text="$200.00", font=('Consolas', 11), background="#252526")
            bal.pack()
            pnl = ttk.Label(f, text="+$0.00", foreground="#00ff00", font=('Consolas', 9), background="#252526")
            pnl.pack()
            # [신규] 사용 중인 증거금 표시 라벨
            margin = ttk.Label(f, text="Used: $0.00", foreground="#ffcc00", font=('Consolas', 9), background="#252526")
            margin.pack()
            
            self.ex_labels[ex.lower()] = {'bal': bal, 'pnl': pnl, 'margin': margin}

        # === 3. 중앙 메인 ===
        center_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        center_paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        pos_frame = ttk.LabelFrame(center_paned, text="⚡ Active Positions", padding=5)
        center_paned.add(pos_frame, weight=1)
        
        cols = ("Ticker", "Long Ex", "Short Ex", "Entry Price", "Current PnL", "Duration")
        self.pos_tree = ttk.Treeview(pos_frame, columns=cols, show="headings", height=8)
        for c in cols: self.pos_tree.heading(c, text=c)
        self.pos_tree.column("Ticker", width=80)
        self.pos_tree.pack(fill=tk.BOTH, expand=True)

        log_frame = ttk.LabelFrame(center_paned, text="📜 Logs", padding=5)
        center_paned.add(log_frame, weight=1)
        
        self.log_area = scrolledtext.ScrolledText(log_frame, height=8, bg="#111", fg="#0f0", font=('Consolas', 9), state='disabled')
        self.log_area.pack(fill=tk.BOTH, expand=True)
        self.log_area.tag_config("INFO", foreground="#cccccc")
        self.log_area.tag_config("WARN", foreground="orange")
        self.log_area.tag_config("ERROR", foreground="#ff5555")
        self.log_area.tag_config("TRADE", foreground="#00ff00", font=('Consolas', 9, 'bold'))

        # === 4. 하단 마켓 데이터 ===
        market_frame = ttk.LabelFrame(self.root, text="📊 Market Watch", padding=5)
        market_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        m_cols = ("Ticker", "HL", "GRVT", "PAC", "EXT", "LTR", "Spread", "Status")
        self.market_tree = ttk.Treeview(market_frame, columns=m_cols, show="headings")
        widths = [80, 80, 80, 80, 80, 80, 80, 80]
        for c, w in zip(m_cols, widths):
            self.market_tree.heading(c, text=c)
            self.market_tree.column(c, width=w, anchor="center")
        
        vsb = ttk.Scrollbar(market_frame, orient="vertical", command=self.market_tree.yview)
        self.market_tree.configure(yscrollcommand=vsb.set)
        self.market_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.market_tree.tag_configure("opp", background="#1e3a29", foreground="#55ff55")
        self.market_tree.tag_configure("wait", background="#252526", foreground="#aaaaaa")

    def _process_logs(self):
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

    def _update_ui(self):
        if not self.bot_instance or not self.is_running:
            self.root.after(1000, self._update_ui)
            return

        try:
            vp = self.bot_instance.virtual_portfolio
            total_equity = 0
            total_init = 0
            
            # 1. 거래소별 자산 및 증거금 업데이트
            for ex_name, label_map in self.ex_labels.items():
                key = ex_name.lower()
                
                # Equity = Available Balance + Locked Margin
                equity = vp.get_total_equity(key)
                locked = vp.locked_margins.get(key, 0.0) # 사용 중인 증거금
                
                # 초기 자금 (임시 고정값 200, 실제로는 설정에서 가져와야 정확함)
                init = 200.0
                pnl = equity - init
                
                # UI 갱신
                label_map['bal'].config(text=f"${equity:.2f}")
                
                color = "#00ff00" if pnl >= 0 else "#ff5555"
                sign = "+" if pnl >= 0 else ""
                label_map['pnl'].config(text=f"{sign}${pnl:.2f}", foreground=color)
                
                # [신규] Used Margin 표시
                label_map['margin'].config(text=f"Used: ${locked:.2f}")
                
                total_equity += equity
                total_init += init
            
            # 전체 요약
            total_pnl = total_equity - total_init
            pnl_pct = (total_pnl / total_init) * 100 if total_init > 0 else 0
            
            self.lbl_total_bal.config(text=f"Total Equity: ${total_equity:.2f}")
            sign = "+" if total_pnl >= 0 else ""
            color = "#00ff00" if total_pnl >= 0 else "#ff5555"
            self.lbl_total_pnl.config(text=f"PnL: {sign}${total_pnl:.2f} ({sign}{pnl_pct:.2f}%)", foreground=color)
            
            trade_count = len(self.bot_instance.recorder.trade_log)
            self.lbl_total_trades.config(text=f"Trades: {trade_count}")

            # 2. 활성 포지션
            for item in self.pos_tree.get_children(): self.pos_tree.delete(item)
            
            positions = vp.positions
            active_tickers = set()
            for ex in positions:
                for t in positions[ex]: active_tickers.add(t)
            
            current_time = time.time()
            for t in active_tickers:
                pos_info = vp.get_active_position(t)
                if pos_info:
                    long = pos_info['long']
                    short = pos_info['short']
                    duration = int(current_time - long['data']['entry_time'])
                    entry_price = f"L:${long['data']['price']:.2f} | S:${short['data']['price']:.2f}"
                    
                    self.pos_tree.insert("", "end", values=(
                        t, long['ex'].upper(), short['ex'].upper(), entry_price, "Running", f"{duration}s"
                    ))

            # 3. 마켓 데이터
            cache = self.bot_instance.market_cache
            sorted_tickers = sorted(cache.keys())
            
            for ticker in sorted_tickers:
                data = cache[ticker]
                def get_p(ex):
                    val = data.get(ex, {}).get('bid', 0)
                    return f"{val:.2f}" if val > 0 else "---"
                
                hl, grvt, pac, ext, ltr = get_p('hyperliquid'), get_p('grvt'), get_p('pacifica'), get_p('extended'), get_p('lighter')
                
                prices = [d['bid'] for d in data.values() if 'bid' in d and d['bid'] > 0]
                spread_str = "0.00%"; status = "WAIT"; tag = "wait"
                
                if len(prices) >= 2:
                    min_p, max_p = min(prices), max(prices)
                    spread = ((max_p - min_p) / min_p) * 100
                    spread_str = f"{spread:.2f}%"
                    if spread > 0.5: status = "🟢 OPP"; tag = "opp"
                
                values = (ticker, hl, grvt, pac, ext, ltr, spread_str, status)
                
                if ticker in self.tree_items:
                    self.market_tree.item(self.tree_items[ticker], values=values, tags=(tag,))
                else:
                    item_id = self.market_tree.insert("", "end", values=values, tags=(tag,))
                    self.tree_items[ticker] = item_id

        except Exception as e:
            pass
            
        self.root.after(1000, self._update_ui)

    def start_bot(self):
        if self.is_running: return
        self.is_running = True
        self.btn_start.config(state="disabled")
        self.btn_stop.config(state="normal")
        self.lbl_status.config(text="● RUNNING", foreground="#00ff00")
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
        logging.info("🛑 Stopping bot...")

    def export_excel(self):
        if self.bot_instance:
            self.bot_instance.save_excel()
            logging.info("엑셀 내보내기 요청됨.")
        else:
            logging.warning("봇이 초기화되지 않았습니다.")

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