# GRVT-Lighter Hedging Bot

This bot implements a cross-hedging strategy between GRVT and Lighter.

## Setup

1.  **Configuration**:
    - Open `src/GRVT_Lighter_Bot/config.py`
    - Fill in your API keys (`GRVT_API_KEY`, `LIGHTER_API_KEY`, etc.)
    - Adjust `ORDER_AMOUNT`, `SPREAD_BPS`, etc.

2.  **SDKs**:
    - The bot assumes SDKs are located in `d:\4_Personal_HONG\Python\VIBE_CODING\sdks`.
    - If they are elsewhere, update `main.py`.

3.  **Running**:
    ```bash
    python -m src.GRVT_Lighter_Bot.main
    ```
    Note: You must run this from the `Arbitrage-Project` root directory (the parent of `src`).

## Features

- **Funding Rate Monitor**: Fetches funding rates from GRVT (via `fetch_ticker`) and Lighter (via `funding_api`).
- **Strategy Loop**: Checks for funding rate spread > `FUNDING_DIFF_THRESHOLD`.
- **Placeholder Execution**: Order placement logic is structured but requires final parameter tuning and risk check enablement.

## Files

- `config.py`: Configuration.
- `main.py`: Entry point.
- `strategy.py`: Core logic loop.
- `exchanges/`: API wrappers.
