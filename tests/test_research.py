import pandas as pd
import pytest

from backtester.backtester import Backtester
from backtester.performance import PerformanceAnalyzer
from main import run_study
from strategies.momentum import MomentumStrategy


def test_momentum_uses_only_the_current_and_past_closes():
    data = pd.DataFrame({"Close": [100, 120, 110, 90, 110]})
    result = MomentumStrategy(data, lookback=2).generate_signals()

    # the signal stays off during warm-up and when the trailing return is zero
    assert result["Signal"].tolist() == [0, 0, 1, 0, 0]
    assert result.loc[2, "Momentum"] == pytest.approx(0.10)


def test_transaction_costs_are_charged_on_both_sides_and_reruns_reset():
    data = pd.DataFrame({"Open": [100, 100], "Close": [100, 100], "Signal": [0, 0]})
    backtester = Backtester(data, initial_cash=1000, cost_bps=10, fractional_shares=True)

    # buy on the first open using the prior signal and sell at the second open
    result = backtester.run(first_execution_signal=1)
    units = 1000 / 100.1
    assert result["Trade"].tolist() == ["BUY", "SELL"]
    assert result["Fee"].tolist() == pytest.approx([units * 0.10] * 2)
    assert result["Portfolio_Value"].tolist() == pytest.approx([units * 100, units * 99.9])
    pd.testing.assert_frame_equal(result, backtester.run(first_execution_signal=1))


def test_whole_share_portfolio_can_afford_fees():
    data = pd.DataFrame({"Open": [100], "Close": [100], "Signal": [1]})
    backtester = Backtester(data, initial_cash=1000, cost_bps=10)
    result = backtester.run(first_execution_signal=1)

    # 10 shares would fit before fees. With fees, the portfolio can buy only nine.
    assert result.loc[0, "Shares"] == 9
    assert backtester.portfolio.cash == pytest.approx(99.1)


def test_drawdown_includes_starting_cash_and_cagr_uses_elapsed_days():
    result = pd.DataFrame({
        "Date": pd.to_datetime(["2023-01-01", "2024-01-01"]),
        "Portfolio_Value": [9000, 11000],
    })
    performance = PerformanceAnalyzer(result)
    assert performance.get_max_drawdown() == pytest.approx(-10)
    assert performance.get_annualized_return() == pytest.approx((1.1 ** (365.25 / 365) - 1) * 100)
    daily_returns = pd.Series([-0.10, 11000 / 9000 - 1])
    assert performance.get_sharpe_ratio() == pytest.approx(
        252 ** 0.5 * daily_returns.mean() / daily_returns.std()
    )


def test_benchmark_buys_at_first_open_and_uses_same_cost_model():
    # deliberately make first-session closing prices differ from the opening prices
    dates = pd.to_datetime([
        "2016-08-31", "2016-09-01", "2023-09-01", "2026-08-31",
    ])
    market_data = pd.DataFrame({
        "Date": dates, "Open": [100, 100, 200, 300], "Close": [100, 120, 220, 310],
    })
    summary, equity, trades = run_study(market_data, cost_bps=10)
    benchmark = summary.loc[
        (summary["Strategy"] == "AAPL buy-and-hold") & (summary["Cost_bps"] == 10)
    ]
    assert benchmark["Final_Value"].tolist() == pytest.approx([
        10_000 * 310 / (100 * 1.001), 10_000 * 310 / (200 * 1.001),
    ])
    assert benchmark["Trades"].tolist() == [1, 1]
    assert len(equity) == 15
    assert trades["Units_Traded"].tolist() == pytest.approx([
        10_000 / (100 * 1.001), 10_000 / (200 * 1.001),
    ])
