"""Entry point for the Forex Trading Bot."""

from __future__ import annotations

import argparse

from src.config import BotConfig
from src.utils.logger import setup_logger


def main() -> None:
    parser = argparse.ArgumentParser(description="Forex Trading Bot")
    parser.add_argument(
        "mode",
        choices=["live", "backtest"],
        default="live",
        nargs="?",
        help="Run mode: 'live' for trading, 'backtest' for historical testing",
    )
    parser.add_argument("--symbol", type=str, default=None, help="Override trading symbol")
    parser.add_argument("--timeframe", type=str, default=None, help="Override timeframe")
    parser.add_argument(
        "--data", type=str, default=None, help="CSV file for backtesting (optional)"
    )
    parser.add_argument(
        "--bars", type=int, default=5000, help="Number of synthetic bars for backtest"
    )
    parser.add_argument(
        "--strategies",
        type=str,
        default=None,
        help="Comma-separated strategies to use (e.g., trend_following,breakout)",
    )

    args = parser.parse_args()
    config = BotConfig()

    if args.symbol:
        config.trading.symbols = args.symbol
    if args.timeframe:
        config.trading.timeframe = args.timeframe
    if args.strategies:
        config.strategy.active_strategies = args.strategies

    if args.mode == "backtest":
        run_backtest(config, args.data, args.bars)
    else:
        run_live(config)


def run_live(config: BotConfig) -> None:
    """Start the live trading bot."""
    from src.bot import ForexBot

    setup_logger("forex_bot", config.log.log_level, config.log.log_file)

    bot = ForexBot(config)
    bot.run()


def run_backtest(config: BotConfig, data_file: str | None, num_bars: int) -> None:
    """Run a backtest."""
    from src.backtesting.data_loader import generate_synthetic_data, load_csv
    from src.backtesting.engine import BacktestEngine
    from src.backtesting.visualizer import plot_results

    setup_logger("forex_bot", "INFO")

    logger = setup_logger("forex_bot", "INFO")
    logger.info("Starting backtest...")

    # Load data
    symbols = config.trading.symbol_list
    symbol = symbols[0] if symbols else "EURUSD"
    pip_size = 0.01 if "JPY" in symbol else 0.0001

    if data_file:
        data = load_csv(data_file)
    else:
        logger.info("No data file provided, generating synthetic data (%d bars)", num_bars)
        data = generate_synthetic_data(
            symbol=symbol,
            num_bars=num_bars,
            seed=42,
        )

    # Run backtest
    engine = BacktestEngine(config)
    result = engine.run(data, symbol=symbol, pip_size=pip_size)

    # Print results
    print(result.summary())

    # Generate chart
    chart_path = plot_results(result)
    if chart_path:
        logger.info("Chart saved to: %s", chart_path)

    # Quality assessment
    print("\n--- STRATEGY ASSESSMENT ---")
    if result.win_rate >= 45 and result.profit_factor >= 1.3 and result.max_drawdown_pct <= 20:
        print("PASS: Strategy meets minimum requirements for forward testing")
    else:
        issues = []
        if result.win_rate < 45:
            issues.append(f"Win rate too low ({result.win_rate:.1f}% < 45%)")
        if result.profit_factor < 1.3:
            issues.append(f"Profit factor too low ({result.profit_factor:.2f} < 1.3)")
        if result.max_drawdown_pct > 20:
            issues.append(f"Max drawdown too high ({result.max_drawdown_pct:.1f}% > 20%)")
        print("REVIEW NEEDED:")
        for issue in issues:
            print(f"  - {issue}")


if __name__ == "__main__":
    main()
