"""Backtest result visualization using matplotlib."""

from __future__ import annotations

from pathlib import Path

from src.backtesting.engine import BacktestResult
from src.utils.logger import get_logger

logger = get_logger("forex_bot.visualizer")


def plot_results(result: BacktestResult, output_dir: str = "reports") -> str | None:
    """
    Generate backtest report charts. Returns path to saved figure.
    Requires matplotlib (install with: pip install forex-trading-bot[backtest])
    """
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        logger.warning("matplotlib not installed. Skipping chart generation.")
        return None

    fig, axes = plt.subplots(3, 1, figsize=(14, 10), height_ratios=[3, 1, 1])
    fig.suptitle("Backtest Results", fontsize=14, fontweight="bold")

    # 1. Equity Curve
    ax1 = axes[0]
    ax1.plot(result.equity_curve, linewidth=1.2, color="#2196F3")
    ax1.axhline(
        y=result.initial_balance, color="gray", linestyle="--", alpha=0.5, label="Initial"
    )
    ax1.fill_between(
        range(len(result.equity_curve)),
        result.initial_balance,
        result.equity_curve,
        alpha=0.1,
        color="#2196F3",
    )
    ax1.set_title("Equity Curve")
    ax1.set_ylabel("Balance ($)")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # 2. Drawdown
    ax2 = axes[1]
    equity = result.equity_curve
    peak = [equity[0]]
    for e in equity[1:]:
        peak.append(max(peak[-1], e))
    drawdown = [(p - e) / p * 100 if p > 0 else 0 for p, e in zip(peak, equity)]
    ax2.fill_between(range(len(drawdown)), drawdown, alpha=0.4, color="#F44336")
    ax2.set_title("Drawdown (%)")
    ax2.set_ylabel("DD %")
    ax2.invert_yaxis()
    ax2.grid(True, alpha=0.3)

    # 3. Trade P&L Distribution
    ax3 = axes[2]
    profits = [t.profit for t in result.trades]
    if profits:
        colors = ["#4CAF50" if p > 0 else "#F44336" for p in profits]
        ax3.bar(range(len(profits)), profits, color=colors, width=1.0)
    ax3.set_title("Trade P&L")
    ax3.set_ylabel("Profit ($)")
    ax3.set_xlabel("Trade #")
    ax3.axhline(y=0, color="black", linewidth=0.5)
    ax3.grid(True, alpha=0.3)

    plt.tight_layout()

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    filepath = output_path / "backtest_report.png"
    fig.savefig(filepath, dpi=150, bbox_inches="tight")
    plt.close(fig)

    logger.info("Backtest report saved to %s", filepath)
    return str(filepath)
