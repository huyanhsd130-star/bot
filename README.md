# Forex Trading Bot

Bot giao dịch Forex tự động với nhiều chiến lược, quản lý rủi ro, backtesting và thông báo qua Telegram.

## Tính Năng

- **3 Chiến lược giao dịch**:
  - **Trend Following**: Kết hợp EMA + MACD + RSI + ATR
  - **Mean Reversion**: Bollinger Bands + RSI trong thị trường sideway
  - **Breakout**: Price channel breakout với xác nhận ATR
- **Quản lý rủi ro toàn diện**:
  - Position sizing tự động (% risk per trade)
  - Stop Loss / Take Profit dựa trên ATR
  - Trailing stop với partial close
  - Giới hạn drawdown, daily/weekly loss
  - Correlation filter (tránh mở quá nhiều cặp tương quan)
- **Backtesting engine**: Test chiến lược trên dữ liệu lịch sử hoặc synthetic data
- **Hỗ trợ nhiều broker**: Demo (paper trading), OANDA, MetaTrader 5
- **Telegram alerts**: Thông báo real-time khi mở/đóng lệnh
- **Session filter**: Chỉ trade trong phiên London/New York

## Cài Đặt

```bash
# Clone repo
git clone <repo-url>
cd forex-trading-bot

# Cài đặt dependencies
pip install -e ".[all]"

# Hoặc cài từng phần
pip install -e .                    # Core only
pip install -e ".[backtest]"       # + Backtesting charts
pip install -e ".[telegram]"       # + Telegram alerts
pip install -e ".[oanda]"          # + OANDA broker
```

## Cấu Hình

```bash
# Copy file cấu hình mẫu
cp .env.example .env

# Chỉnh sửa .env theo nhu cầu
```

### Các tham số quan trọng

| Tham số | Mặc định | Mô tả |
|---------|----------|-------|
| `BROKER_TYPE` | `demo` | Loại broker: `demo`, `oanda`, `mt5` |
| `SYMBOLS` | `EURUSD,GBPUSD` | Cặp tiền giao dịch |
| `TIMEFRAME` | `H1` | Khung thời gian |
| `RISK_PER_TRADE` | `1.0` | % rủi ro mỗi lệnh |
| `MAX_OPEN_TRADES` | `3` | Số lệnh mở tối đa |
| `MAX_DAILY_LOSS_PCT` | `5.0` | % lỗ tối đa/ngày |
| `MAX_DRAWDOWN_PCT` | `20.0` | % drawdown tối đa (dừng bot) |
| `RR_RATIO` | `2.0` | Tỷ lệ Risk:Reward |
| `ACTIVE_STRATEGIES` | `trend_following` | Chiến lược sử dụng |

## Sử Dụng

### 1. Paper Trading (Demo)

```bash
# Chạy với broker demo (không cần tài khoản thật)
python -m src.main live
```

### 2. Backtesting

```bash
# Backtest với dữ liệu synthetic (5000 bars)
python -m src.main backtest

# Backtest với file CSV
python -m src.main backtest --data data/EURUSD_H1.csv

# Backtest với nhiều chiến lược
python -m src.main backtest --strategies trend_following,breakout --bars 10000

# Backtest trên cặp JPY
python -m src.main backtest --symbol USDJPY --bars 5000
```

### 3. Live Trading (OANDA)

```bash
# Cấu hình trong .env
BROKER_TYPE=oanda
OANDA_API_KEY=your-api-key
OANDA_ACCOUNT_ID=your-account-id
OANDA_ENVIRONMENT=practice  # hoặc 'live'

# Chạy
python -m src.main live
```

### 4. Telegram Alerts

```bash
# Cấu hình trong .env
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_CHAT_ID=your-chat-id
```

Cách lấy bot token:
1. Tìm `@BotFather` trên Telegram
2. Gửi `/newbot` và làm theo hướng dẫn
3. Copy token vào `.env`

Cách lấy chat ID:
1. Gửi tin nhắn cho bot
2. Truy cập `https://api.telegram.org/bot<TOKEN>/getUpdates`
3. Tìm `chat.id` trong response

## Kiến Trúc

```
forex-trading-bot/
├── src/
│   ├── data/              # Data models & Broker implementations
│   │   ├── models.py      # Trade, Signal, Candle models
│   │   ├── broker_base.py # Abstract broker interface
│   │   ├── demo_broker.py # Paper trading broker
│   │   └── oanda_broker.py# OANDA REST API broker
│   ├── indicators/        # Technical indicators
│   │   └── technical.py   # EMA, RSI, MACD, ATR, Bollinger
│   ├── strategies/        # Trading strategies
│   │   ├── base.py        # Strategy interface
│   │   ├── trend_following.py
│   │   ├── mean_reversion.py
│   │   └── breakout.py
│   ├── risk/              # Risk management
│   │   └── manager.py     # Position sizing, drawdown control
│   ├── execution/         # Order execution
│   │   └── trade_manager.py
│   ├── backtesting/       # Backtesting engine
│   │   ├── engine.py      # Core backtest logic
│   │   ├── data_loader.py # CSV & synthetic data
│   │   └── visualizer.py  # Chart generation
│   ├── alerts/            # Notifications
│   │   └── telegram_alert.py
│   ├── utils/             # Utilities
│   │   ├── logger.py
│   │   └── time_utils.py
│   ├── bot.py             # Main bot orchestrator
│   ├── config.py          # Configuration management
│   └── main.py            # Entry point
├── tests/                 # Unit tests
├── .env.example           # Environment template
├── pyproject.toml         # Project config & dependencies
└── README.md
```

## Logic Chiến Lược

### Trend Following

```
BUY khi:
  ✓ Price > EMA 200 (uptrend dài hạn)
  ✓ EMA 20 > EMA 50 (uptrend trung hạn)
  ✓ MACD crossover lên (momentum)
  ✓ RSI 40-70 (không overbought)
  ✓ ATR đủ lớn (đủ biến động)

SELL: Điều kiện ngược lại
```

### Mean Reversion

```
BUY khi:
  ✓ Price chạm/dưới Bollinger Band dưới
  ✓ RSI < 30 (oversold)
  ✓ Thị trường sideway (EMA flat)

Target: Quay về middle Bollinger Band
```

### Breakout

```
BUY khi:
  ✓ Price phá vỡ đỉnh cao nhất N cây nến
  ✓ ATR xác nhận biến động đủ lớn

SELL: Phá vỡ đáy thấp nhất N cây nến
```

## Quản Lý Rủi Ro

| Quy tắc | Giá trị mặc định |
|---------|-------------------|
| Risk per trade | 1% balance |
| Max open trades | 3 |
| Max daily loss | 5% |
| Max weekly loss | 10% |
| Max drawdown | 20% (dừng bot) |
| Min R:R ratio | 1:2 |
| Trailing stop | Kích hoạt tại 1:1 R:R |
| Partial close | 50% tại 1:1, dời SL về breakeven |

## Tests

```bash
# Chạy tất cả tests
pytest

# Chạy với coverage
pytest --tb=short -v
```

## Lưu Ý

- **Đây KHÔNG phải lời khuyên đầu tư.** Trading forex có rủi ro cao.
- Luôn **backtest** kỹ trước khi chạy live.
- Bắt đầu với **tài khoản demo** trước.
- Bắt đầu live với **lot size nhỏ nhất** (0.01).
- Không có chiến lược nào thắng 100%. Mục tiêu là có **edge** bền vững.

## License

MIT
