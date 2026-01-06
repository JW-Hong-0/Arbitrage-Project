import math
from decimal import Decimal, ROUND_FLOOR

class Utils:
    @staticmethod
    def normalize_symbol(exchange: str, symbol: str) -> str:
        """
        Normalizes symbol to exchange specific format.
        Input symbol: 'BTC', 'ETH' (Base Asset)
        
        GRVT: 'BTC_USDT_Perp'
        Lighter: 'BTC-USDT'
        """
        base = symbol.upper().split('_')[0].split('-')[0]
        
        if exchange.lower() == 'grvt':
            return f"{base}_USDT_Perp"
        elif exchange.lower() == 'lighter':
            return f"{base}-USDT"
        return base

    @staticmethod
    def quantize_amount(amount: float, tick_size: float) -> float:
        """
        Rounds down amount to the nearest tick_size.
        """
        if tick_size <= 0: return amount
        
        # Avoid float precision issues by string conversion
        d_amount = Decimal(str(amount))
        d_tick = Decimal(str(tick_size))
        
        # Round down to nearest tick
        quantized = (d_amount // d_tick) * d_tick
        return float(quantized)

    @staticmethod
    def calc_precision(tick_size: float) -> int:
        """
        Calculates decimal precision from tick size.
        e.g. 0.001 -> 3
        """
        if tick_size <= 0: return 0
        return int(round(-math.log10(tick_size), 0))
