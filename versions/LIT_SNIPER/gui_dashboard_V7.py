import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, Menu, PanedWindow
import asyncio
import logging
import queue
import threading
import sys
import time
from datetime import datetime

try:
    from arbitrage_bot import ArbitrageBot
    import settings
except ImportError:
    messagebox.showerror("Error", "arbitrage_bot.py를 찾을 수 없습니다.")
    sys.exit(1)

# 로그 필터링
for lib in ["pysdk", "GrvtCcxtWS", "websockets", "urllib3", "asyncio", "MARKET_SYNC"]:
    logging.getLogger(lib).setLevel(logging.CRITICAL)

class QueueHandler(logging.Handler):
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue
        self.setFormatter(logging.Formatter('%(asctime)s %(message)s', datefmt='%H:%M:%S'))

    def emit(self, record):
        try:
            msg = self.format(record)
            self.log_queue.put((record.levelno, msg))
        except: pass

class ArbitrageDashboard:
    def __init__(self, root):
        self.root = root
        self.root.title("Arbitrage Bot V12 (Auto-Exit Monitor)")
        self.root.geometry("1600x950")
        self.root.configure(bg="#1e1e1e")

        self._setup_styles()
        self.log_queue = queue.Queue()
        self._setup_logging()
        
        self.bot_instance = None
        self.is_running = False
        self.start_time = None

        self._create_menu()
        self._init_layout()
        self.update_ui_loop()

    def _setup_styles(self):
        self.style = ttk.Style()
        self.style.theme_use('clam')
        colors = {'bg': '#1e1e1e', 'fg': 'white', 'dark': '#252526', 'gray': '#333333', 'accent': '#007acc'}
        
        self.style.configure("TFrame", background=colors['bg'])
        self.style.configure("TLabelframe", background=colors['bg'], foreground='white', relief="solid")
        self.style.configure("TLabelframe.Label", background=colors['bg'], foreground="#cccccc", font=("Segoe UI", 10, "bold"))
        self.style.configure("TLabel", background=colors['bg'], foreground='white', font=("Segoe UI", 9))
        self.style.configure("Treeview", background=colors['dark'], foreground='white', fieldbackground=colors['dark'], borderwidth=0, font=("Consolas", 10))
        self.style.configure("Treeview.Heading", background=colors['gray'], foreground='white', relief="flat", font=("Segoe UI", 9, "bold"))
        self.style.map("Treeview.Heading", background=[('active', '#404040')])

    def _setup_logging(self):
        self.logger = logging.getLogger()
        self.logger.setLevel(logging.INFO)
        for h in self.logger.handlers[:]: self.logger.removeHandler(h)
        self.logger.addHandler(QueueHandler(self.log_queue))
        self.logger.addHandler(logging.StreamHandler(sys.stdout))

    def _create_menu(self):
        menubar = Menu(self.root)
        self.root.config(menu=menubar)
        tools = Menu(menubar, tearoff=0)
        menubar.add_cascade(label="🛠️ Tools", menu=tools)
        tools.add_command(label="📊 Market Info (티커 정보)", command=self.open_market_info)
        tools.add_command(label="⚙️ Settings (설정 편집)", command=self.open_settings)

    def _init_layout(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(2, weight=1) 

        # 1. Top Section
        top_container = ttk.Frame(self.root)
        top_container.grid(row=0, column=0, sticky="ew", padx=10, pady=5)
        top_container.columnconfigure(1, weight=1)

        # Controls
        ctrl_frame = ttk.LabelFrame(top_container, text="Control")
        ctrl_frame.grid(row=0, column=0, sticky="ns", padx=5)
        self.btn_start = tk.Button(ctrl_frame, text="▶ START", command=self.start_bot, bg="#2d2d2d", fg="white", width=12, font=("Segoe UI", 9, "bold"))
        self.btn_start.pack(side="left", padx=10, pady=10)
        self.btn_stop = tk.Button(ctrl_frame, text="⏹ STOP", command=self.stop_bot, bg="#2d2d2d", fg="white", width=12, font=("Segoe UI", 9, "bold"), state="disabled")
        self.btn_stop.pack(side="left", padx=10, pady=10)
        self.lbl_status = ttk.Label(ctrl_frame, text="● READY", font=("Segoe UI", 11, "bold"), foreground="gray")
        self.lbl_status.pack(side="left", padx=20)

        # Summary
        sum_frame = ttk.LabelFrame(top_container, text="Performance Summary")
        sum_frame.grid(row=0, column=1, sticky="nsew", padx=5)
        self.vars = {
            "Initial": tk.StringVar(value="-"), "Current": tk.StringVar(value="-"),
            "PnL": tk.StringVar(value="-"), "Time": tk.StringVar(value="-")
        }
        for i, (k, v) in enumerate(self.vars.items()):
            f = ttk.Frame(sum_frame); f.pack(side="left", expand=True, fill="both", padx=10)
            ttk.Label(f, text=k, foreground="#888", font=("Segoe UI", 8)).pack(anchor="w")
            ttk.Label(f, textvariable=v, foreground="#007acc", font=("Segoe UI", 14, "bold")).pack(anchor="w")

        # 2. Exchange Portfolio
        ex_frame = ttk.LabelFrame(self.root, text="Exchange Portfolio")
        ex_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        cols = ["Metric", "HL", "GRVT", "PAC", "LTR", "EXT", "TOTAL"]
        self.tree_ex = ttk.Treeview(ex_frame, columns=cols, show="headings", height=4)
        for c in cols:
            self.tree_ex.heading(c, text=c); self.tree_ex.column(c, width=120, anchor="center")
        self.tree_ex.pack(fill="x", padx=5, pady=5)

        # 3. Resizable Main Area
        main_pane = PanedWindow(self.root, orient=tk.VERTICAL, sashrelief=tk.RAISED, sashwidth=6, bg="#333333")
        main_pane.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)

        # Pane 1: Active Positions (Top) - [수정] Current Spread 컬럼 추가
        pos_frame = ttk.LabelFrame(main_pane, text="Active Positions (Live)")
        pos_cols = ["Ticker", "Qty", "Long Ex", "Short Ex", "Entry Spread", "Current Spread", "Duration"]
        self.tree_pos = ttk.Treeview(pos_frame, columns=pos_cols, show="headings")
        for c in pos_cols:
            self.tree_pos.heading(c, text=c); self.tree_pos.column(c, width=110, anchor="center")
        self.tree_pos.pack(fill="both", expand=True)
        main_pane.add(pos_frame, height=200)

        # Pane 2: Market Watch (Middle)
        mkt_frame = ttk.LabelFrame(main_pane, text="Market Watch (Mid-Price Monitor)")
        mkt_scroll = ttk.Scrollbar(mkt_frame, orient="vertical")
        mkt_scroll.pack(side="right", fill="y")
        mkt_cols = ["Ticker", "HL", "GRVT", "PAC", "LTR", "EXT", "Spread", "Route"]
        self.tree_mkt = ttk.Treeview(mkt_frame, columns=mkt_cols, show="headings", yscrollcommand=mkt_scroll.set)
        for c in mkt_cols:
            self.tree_mkt.heading(c, text=c); self.tree_mkt.column(c, width=80, anchor="center")
        mkt_scroll.config(command=self.tree_mkt.yview)
        self.tree_mkt.pack(fill="both", expand=True)
        main_pane.add(mkt_frame, height=350)

        # Pane 3: System Log (Bottom)
        log_frame = ttk.LabelFrame(main_pane, text="System Log")
        self.log_area = scrolledtext.ScrolledText(log_frame, state='disabled', height=6, bg="#252526", fg="white", font=("Consolas", 10))
        self.log_area.pack(fill="both", expand=True)
        self.log_area.tag_config("INFO", foreground="white")
        self.log_area.tag_config("WARNING", foreground="orange")
        self.log_area.tag_config("ERROR", foreground="#ff5555")
        self.log_area.tag_config("SUCCESS", foreground="#00ff00")
        main_pane.add(log_frame, height=150)

    # --- Popups ---
    def open_market_info(self):
        if not self.bot_instance or not self.bot_instance.market_sync:
            return messagebox.showwarning("Info", "봇 실행 후 예열 완료 필요")
        top = tk.Toplevel(self.root)
        top.title("Market Info"); top.geometry("900x600"); top.configure(bg="#1e1e1e")
        cols = ("Ticker", "Min Qty", "Precision", "Max Lev", "Size($)")
        tree = ttk.Treeview(top, columns=cols, show="headings")
        for c in cols: tree.heading(c, text=c); tree.column(c, width=120, anchor="center")
        tree.pack(fill="both", expand=True, padx=10, pady=10)
        for r in self.bot_instance.get_market_summary():
            tree.insert("", "end", values=(r['Ticker'], r.get('Min_Qty'), r.get('Precision'), r.get('Max_Lev'), r.get('Size($)')))

    def open_settings(self):
        top = tk.Toplevel(self.root)
        top.title("Settings Editor"); top.geometry("1000x600"); top.configure(bg="#1e1e1e")
        cols = ("Ticker", "Size($)", "Max Margin($)", "Leverage", "Strategy")
        tree = ttk.Treeview(top, columns=cols, show="headings")
        for c in cols: tree.heading(c, text=c); tree.column(c, width=150, anchor="center")
        tree.pack(fill="both", expand=True, padx=10, pady=10)

        for t, c in settings.TARGET_PAIRS_CONFIG.items():
            tree.insert("", "end", iid=t, values=(t, c.get('trade_size_fixed_usd'), c.get('max_margin_usd', 15.0), c.get('target_leverage', 15), c.get('strategy_preset')))

        def on_double_click(event):
            item = tree.selection()[0]
            col = tree.identify_column(event.x)
            col_idx = int(col.replace('#', '')) - 1
            if col_idx < 0: return 
            x, y, w, h = tree.bbox(item, col)
            val = tree.item(item, 'values')[col_idx]
            entry = tk.Entry(tree); entry.place(x=x, y=y, width=w, height=h); entry.insert(0, val); entry.focus()

            def save(e):
                new_val = entry.get()
                current_vals = list(tree.item(item, 'values'))
                current_vals[col_idx] = new_val
                tree.item(item, values=current_vals)
                entry.destroy()
                try:
                    ticker = item
                    if col_idx == 1: settings.TARGET_PAIRS_CONFIG[ticker]['trade_size_fixed_usd'] = float(new_val)
                    elif col_idx == 2: settings.TARGET_PAIRS_CONFIG[ticker]['max_margin_usd'] = float(new_val)
                    elif col_idx == 3: settings.TARGET_PAIRS_CONFIG[ticker]['target_leverage'] = int(new_val)
                    elif col_idx == 4: settings.TARGET_PAIRS_CONFIG[ticker]['strategy_preset'] = new_val
                    print(f"✅ Setting Updated: {ticker} -> {new_val}")
                except Exception as ex: print(f"❌ Update Failed: {ex}")

            entry.bind('<Return>', save); entry.bind('<FocusOut>', lambda e: entry.destroy())
        tree.bind('<Double-1>', on_double_click)

    # --- Updates ---
    def update_ui_loop(self):
        try:
            while not self.log_queue.empty():
                lvl, msg = self.log_queue.get_nowait()
                tag = "INFO"
                if lvl >= logging.ERROR: tag = "ERROR"
                elif lvl >= logging.WARNING: tag = "WARNING"
                elif "✅" in msg or "🚀" in msg or "💰" in msg: tag = "SUCCESS"
                self.log_area.config(state='normal')
                self.log_area.insert(tk.END, msg + "\n", tag)
                self.log_area.see(tk.END)
                self.log_area.config(state='disabled')

            if self.is_running and self.bot_instance:
                self._update_data()
        except: pass
        self.root.after(100, self.update_ui_loop)

    def _update_data(self):
        pm = self.bot_instance.pm
        if not pm or not pm.balance_history: return
        init = pm.balance_history[0]
        curr = pm.balance_history[-1]
        self.vars["Initial"].set(f"${init['Total_Equity']:,.2f}")
        self.vars["Current"].set(f"${curr['Total_Equity']:,.2f}")
        pnl = curr['Total_Equity'] - init['Total_Equity']
        self.vars["PnL"].set(f"${pnl:+.2f}")
        elapsed = int(time.time() - self.start_time)
        self.vars["Time"].set(time.strftime("%H:%M:%S", time.gmtime(elapsed)))

        for i in self.tree_ex.get_children(): self.tree_ex.delete(i)
        exchanges = ["HL", "GRVT", "PAC", "LTR", "EXT"]
        metrics = ["Initial", "Current", "PnL($)", "PnL(%)"]
        for m in metrics:
            vals = [m]; total = 0.0
            for ex in exchanges:
                i_val = init.get(ex, 0); c_val = curr.get(ex, 0)
                if m == "Initial": v = i_val
                elif m == "Current": v = c_val
                elif m == "PnL($)": v = c_val - i_val
                elif m == "PnL(%)": v = ((c_val - i_val)/i_val*100) if i_val > 0 else 0
                if m == "PnL(%)": vals.append(f"{v:+.2f}%")
                else: vals.append(f"${v:,.2f}"); total += v
            if m == "PnL(%)": vals.append("-")
            else: vals.append(f"${total:,.2f}")
            self.tree_ex.insert("", "end", values=vals)

        self._update_market_watch()
        self._update_active_positions()

    def _update_market_watch(self):
        cache = self.bot_instance.bbo_cache
        existing = {self.tree_mkt.item(i)['values'][0]: i for i in self.tree_mkt.get_children()}
        for ticker, data in cache.items():
            hl = self._fmt(data.get('HL'))
            grvt = self._fmt(data.get('GRVT'))
            pac = self._fmt(data.get('PAC'))
            ltr = self._fmt(data.get('LTR'))
            ext = self._fmt(data.get('EXT'))
            
            valid_bids = {k: (data[k]['bid'] + data[k]['ask'])/2 for k in data if data[k]['ask']>0}
            spread = "-"; route = "-"
            if len(valid_bids) >= 2:
                mx_k = max(valid_bids, key=valid_bids.get); mn_k = min(valid_bids, key=valid_bids.get)
                if mx_k != mn_k:
                    s_val = (valid_bids[mx_k] - valid_bids[mn_k]) / valid_bids[mn_k] * 100
                    spread = f"{s_val:+.2f}%"; route = f"{mn_k}→{mx_k}"

            vals = (ticker, hl, grvt, pac, ltr, ext, spread, route)
            if ticker in existing: self.tree_mkt.item(existing[ticker], values=vals)
            else: self.tree_mkt.insert("", "end", values=vals)

    def _update_active_positions(self):
        for i in self.tree_pos.get_children(): self.tree_pos.delete(i)
        for sym, pos in self.bot_instance.active_positions.items():
            dur = int(time.time() - pos['time'])
            # [수정] Current Spread 표시
            curr_spread = pos.get('current_spread', 0)
            self.tree_pos.insert("", "end", values=(
                sym, pos['qty'], pos['long'], pos['short'],
                f"{pos.get('entry_spread', 0):.2f}%", 
                f"{curr_spread:.2f}%", 
                f"{dur}s"
            ))

    def _fmt(self, bbo):
        if not bbo: return "-"
        mid = (bbo['bid'] + bbo['ask']) / 2
        return f"${mid:.4f}"

    def start_bot(self):
        if self.is_running: return
        self.is_running = True
        self.start_time = time.time()
        self.btn_start.config(state="disabled"); self.btn_stop.config(state="normal", bg="#ff5555")
        self.lbl_status.config(text="● RUNNING", foreground="#00ff00")
        threading.Thread(target=self._run_bot, daemon=True).start()

    def _run_bot(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self.bot_instance = ArbitrageBot()
        loop.run_until_complete(self.bot_instance.run())

    def stop_bot(self):
        if self.bot_instance: self.bot_instance.is_running = False
        self.is_running = False
        self.btn_start.config(state="normal"); self.btn_stop.config(state="disabled", bg="#2d2d2d")
        self.lbl_status.config(text="● STOPPED", foreground="red")

if __name__ == "__main__":
    root = tk.Tk()
    app = ArbitrageDashboard(root)
    root.mainloop()