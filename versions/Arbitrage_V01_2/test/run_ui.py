# run_ui.py
# (⭐️ 2025-11-25: v3 - 스레드 안전성 및 CSS 오류 완벽 해결)

import asyncio
import logging
import threading
from datetime import datetime
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, RichLog
from textual.containers import Grid

# 기존 봇 클래스 임포트
try:
    from arbitrage_bot import ArbitrageBot
except ImportError:
    print("❌ 'arbitrage_bot.py' 파일을 찾을 수 없습니다.")
    exit()

# --- 로그 분류기 (Log Handler) ---
class DashboardHandler(logging.Handler):
    """로그를 분석하여 UI의 적절한 위젯으로 보내는 핸들러"""
    def __init__(self, app_instance):
        super().__init__()
        self.app = app_instance
        self.setFormatter(logging.Formatter('%(asctime)s - %(message)s', datefmt='%H:%M:%S'))

    def emit(self, record):
        try:
            msg = self.format(record)
            level = record.levelno
            raw_msg = record.getMessage()
            
            target = "system"
            style = ""

            # 1. 트레이드 로그
            if any(k in raw_msg for k in ["진입", "청산", "주문 실행", "포트폴리오 상태", "💾"]):
                target = "trade"
                style = "bold green" if "수익" in msg or "청산" in msg else "white"
            
            # 2. 에러/경고 로그
            elif level >= logging.WARNING or any(k in raw_msg for k in ["오류", "실패", "Watchdog", "ConnectionClosed", "Traceback", "❌", "🚨"]):
                target = "error"
                style = "bold red"

            # 3. 시스템 로그 (필터링)
            else:
                if "pysdk" in record.name or "websockets" in record.name:
                    return 
                target = "system"

            # ⭐️ [핵심 수정] 스레드 감지 및 안전한 호출
            # 앱이 실행 중이고 메인 루프가 돌아갈 때만 업데이트
            if self.app.is_running:
                self.app.safe_write_log(target, msg, style)
                
        except Exception:
            self.handleError(record)

# --- UI 레이아웃 및 앱 (TUI) ---
class ArbitrageDashboard(App):
    CSS = """
    Grid {
        grid-size: 2 2;
        grid-rows: 1fr 1fr;
        grid-columns: 2fr 1fr;
    }

    #trade_box {
        row-span: 2;
        background: $surface;
        border: solid green;
    }

    #error_box {
        background: $surface;
        border: solid red;
    }

    #system_box {
        background: $surface;
        border: solid blue;
    }
    
    RichLog {
        overflow-x: hidden;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Grid():
            # CSS 타이틀 대신 코드에서 설정
            trade_log = RichLog(id="trade_box", highlight=True, markup=True)
            trade_log.border_title = "📈 Trade & Portfolio Logs"
            yield trade_log

            error_log = RichLog(id="error_box", highlight=True, markup=True)
            error_log.border_title = "🚨 Error & Network Logs"
            yield error_log

            system_log = RichLog(id="system_box", highlight=True, markup=True)
            system_log.border_title = "⚙️ System & Debug Logs"
            yield system_log
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Arbitrage Bot Dashboard (HL/GRVT/PAC)"
        
        # 1. 커스텀 로깅 핸들러 연결
        handler = DashboardHandler(self)
        
        # 루트 로거 설정
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        # 기존 핸들러 제거 (중복 출력 방지)
        for h in root_logger.handlers[:]:
            root_logger.removeHandler(h)
        root_logger.addHandler(handler)
        
        # 봇 로거 설정
        bot_logger = logging.getLogger("ArbitrageBot")
        bot_logger.setLevel(logging.INFO)
        bot_logger.addHandler(handler)

        # 2. 봇 백그라운드 실행
        self.run_worker(self.start_bot_logic(), exclusive=True, thread=True)

    async def start_bot_logic(self):
        self.safe_write_log("system", "🤖 봇 시스템 초기화 중...", style="yellow")
        try:
            # 새 이벤트 루프 생성 (스레드 독립성 보장)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            self.bot = ArbitrageBot(loop)
            await self.bot.start()
        except asyncio.CancelledError:
            self.safe_write_log("system", "🛑 봇 작업이 취소되었습니다.")
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            self.safe_write_log("error", f"❌ 봇 실행 중 치명적 오류:\n{tb}")

    def safe_write_log(self, target: str, message: str, style: str = ""):
        """스레드 안전하게 UI 업데이트를 분기 처리"""
        if style:
            message = f"[{style}]{message}[/]"
            
        # 위젯 찾기
        try:
            if target == "trade":
                widget = self.query_one("#trade_box", RichLog)
            elif target == "error":
                widget = self.query_one("#error_box", RichLog)
            else:
                widget = self.query_one("#system_box", RichLog)
            
            # ⭐️ 현재 스레드가 메인 스레드인지 확인
            if threading.current_thread() is not self._thread_id:
                # 워커 스레드 -> 메인 스레드로 요청
                self.call_from_thread(widget.write, message)
            else:
                # 이미 메인 스레드면 직접 쓰기
                widget.write(message)
        except:
            # 앱 종료 중이거나 위젯이 없을 때 무시
            pass

    async def action_quit(self) -> None:
        """종료 키(q) 눌렀을 때"""
        self.safe_write_log("system", "🛑 종료 요청 확인. 정리 중...", style="bold red")
        if hasattr(self, 'bot'):
            await self.bot.stop()
        self.exit()

if __name__ == "__main__":
    app = ArbitrageDashboard()
    # 메인 스레드 ID 저장 (비교용)
    app._thread_id = threading.current_thread()
    app.run()