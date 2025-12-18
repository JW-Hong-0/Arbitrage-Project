🚀 Crypto Arbitrage Bot Project (Multi-Exchange)
이 프로젝트는 5개 주요 DEX(BASEDAPP, GRVT, PACIFICA, LIGHTER, EXTENDED) 간의 가격 차이(Spread)를 감지하여 자동으로 차익거래를 수행하는 봇을 개발하는 프로젝트입니다.

📜 Version History (개발 일지)
각 버전은 versions/ 폴더 내에 백업되어 있으며, 개발 단계별 주요 기능은 다음과 같습니다.

📂 V01_2 : 웹소켓 연결 및 백테스팅 (WebSocket & Backtest)
Target Exchanges: BASEDAPP, GRVT, PACIFICA, LIGHTER, EXTENDED (5개 거래소)
Key Features:
5개 거래소의 실시간 시세(BBO)를 수신하는 웹소켓(WebSocket) 연결 구현.
차익 기회 포착 시, 실제 주문을 내지 않고 진입/청산 시뮬레이션을 수행하는 백테스트 로직 탑재.
데이터 수집 및 전략 검증 단계.
📂 V01_3 : 주문 로직 통합 1단계 (Execution Phase 1)
Target Exchanges: BASEDAPP, GRVT
Key Features:
시뮬레이션을 넘어 실제 매수(Long) 및 매도(Short) 주문 API 연동.
가장 기본적인 2개 거래소 간의 차익거래 로직 검증 완료.
📂 V01_4 : 주문 로직 통합 2단계 (Execution Phase 2)
Target Exchanges: PACIFICA, LIGHTER, EXTENDED 추가
Key Features:
나머지 3개 거래소에 대한 매수/매도 주문 로직 추가 구현.
5개 거래소 전체에 대한 교차 차익거래(Cross-Exchange Arbitrage) 준비 완료.
📂 V01_5 : 실전 아비트라지 봇 (Live Production Bot)
Current Status: Beta Testing (실전 테스트 중)
Key Features:
5개 거래소 완전 통합 (Full Websocket & Execution Logic).
실시간 가격 데이터를 기반으로 한 실전 매매 로직 가동.
Note: 현재 실전 테스트를 통해 데이터를 축적 중이며, 예외 상황 처리(Error Handling) 및 안정성 확보를 위한 디버깅 진행 중.
🛠 Tech Stack
Language: Python
Core Libs: asyncio, aiohttp, ccxt (or custom SDKs)