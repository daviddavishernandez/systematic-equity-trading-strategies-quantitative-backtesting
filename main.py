import argparse
from math import isfinite
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # save the chart even when the run has no desktop display

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

from utils.data_loader import DataLoader
from utils.download_data import DATA_PATH
from utils.validator import DataValidator
from strategies.momentum import MomentumStrategy
from strategies.moving_average import MovingAverageStrategy
from backtester.backtester import Backtester
from backtester.performance import PerformanceAnalyzer


INITIAL_CASH = 10_000
END_DATE = "2026-08-31"
STUDY_WINDOWS = {"Full sample": "2016-09-01", "Late sample": "2023-09-01"}
DEFAULT_OUTPUT = Path(__file__).resolve().parent / "results"


def load_adjusted_data(path):
    # ---------------------------------------------------
    # LOAD DATA
    # ---------------------------------------------------

    market_data = DataLoader(path).load_data()

    # ---------------------------------------------------
    # VALIDATE DATA
    # ---------------------------------------------------

    DataValidator(market_data).validate()
    if "Adj Close" not in market_data:
        raise ValueError("Research data must include an 'Adj Close' column")
    adjusted_close = pd.to_numeric(market_data["Adj Close"], errors="raise")
    if not adjusted_close.between(0, float("inf"), inclusive="neither").all():
        raise ValueError("Adjusted closes must be positive and finite")

    # apply the same daily adjustment to every price so opening and closing values agree
    adjustment = adjusted_close / market_data["Close"]
    price_columns = ["Open", "High", "Low", "Close"]
    market_data[price_columns] = market_data[price_columns].mul(adjustment, axis=0)
    DataValidator(market_data).validate()

    # the first execution needs a prior signal and 63 earlier trading sessions
    warmup_sessions = (market_data["Date"] < STUDY_WINDOWS["Full sample"]).sum()
    study_sessions = market_data["Date"].between(STUDY_WINDOWS["Full sample"], END_DATE)
    if (
        warmup_sessions < 64
        or study_sessions.sum() != 2512
        or pd.Timestamp(STUDY_WINDOWS["Full sample"]) not in market_data["Date"].values
        or pd.Timestamp(END_DATE) not in market_data["Date"].values
    ):
        raise ValueError("Use all 2,512 study sessions and at least 64 warm-up sessions")
    return market_data


def run_study(market_data, cost_bps):
    # ---------------------------------------------------
    # CREATE STRATEGY
    # ---------------------------------------------------

    strategies = {
        "20/50-day crossover": MovingAverageStrategy(market_data).generate_signals(),
        "63-day momentum": MomentumStrategy(market_data).generate_signals(),
        "AAPL buy-and-hold": market_data.assign(Signal=1),
    }

    # ---------------------------------------------------
    # RUN BACKTEST
    # ---------------------------------------------------

    metrics = []
    equity_curves = []
    trades = []
    sensitivity_costs = sorted({0, cost_bps, 25})
    for period, start_date in STUDY_WINDOWS.items():
        # reset to the same $10,000 at the start of each evaluation window
        for name, signal_data in strategies.items():
            prior_signal = signal_data.loc[signal_data["Date"] < start_date, "Signal"].iloc[-1]
            window = signal_data.loc[signal_data["Date"].between(start_date, END_DATE)]
            for fees in sensitivity_costs if period == "Full sample" else [cost_bps]:
                backtester = Backtester(
                    window, initial_cash=INITIAL_CASH, cost_bps=fees, fractional_shares=True
                )
                results = backtester.run(first_execution_signal=prior_signal)

                # keep daily curves and filled orders for the selected cost scenario
                if fees == cost_bps:
                    labelled = results.assign(Period=period, Strategy=name)
                    equity_curves.append(labelled[[
                        "Period", "Strategy", "Date", "Signal", "Execution_Signal",
                        "Portfolio_Value", "Shares", "Fee",
                    ]])
                    fills = labelled.loc[labelled["Trade"] != "", [
                        "Period", "Strategy", "Date", "Trade", "Open", "Shares", "Fee",
                    ]].copy()
                    # record quantity traded, including the units sold before holdings went to zero
                    previous_shares = results["Shares"].shift(fill_value=0)
                    quantities = results["Shares"].sub(previous_shares).abs()
                    fills["Units_Traded"] = quantities.loc[fills.index]
                    fills = fills.rename(columns={"Open": "Adjusted_Open", "Shares": "Units_Held"})
                    if not fills.empty:
                        trades.append(fills)
                metrics.append(summarize(results, period, name, fees))
    return pd.DataFrame(metrics), pd.concat(equity_curves), pd.concat(trades)


# ---------------------------------------------------
# ANALYZE PERFORMANCE
# ---------------------------------------------------

def summarize(results, period, strategy, cost_bps):
    performance = PerformanceAnalyzer(results, initial_cash=INITIAL_CASH)
    return {
        "Period": period,
        "Strategy": strategy,
        "Cost_bps": cost_bps,
        "Start": results["Date"].iloc[0].date(),
        "End": results["Date"].iloc[-1].date(),
        "Sessions": len(results),
        "Final_Value": performance.get_final_value(),
        "Total_Return_pct": performance.get_total_return(),
        "CAGR_pct": performance.get_annualized_return(),
        "Sharpe": performance.get_sharpe_ratio(),
        "Max_Drawdown_pct": performance.get_max_drawdown(),
        "Trades": results["Trade"].ne("").sum(),
        "Fees_USD": results["Fee"].sum(),
        "Exposure_pct": results["Shares"].gt(0).mean() * 100,
    }


# ---------------------------------------------------
# DISPLAY RESULTS
# ---------------------------------------------------

def save_results(metrics, equity, trades, output, cost_bps):
    output.mkdir(parents=True, exist_ok=True)
    metrics.to_csv(output / "summary.csv", index=False, float_format="%.6f")
    equity.to_csv(output / "equity_curves.csv", index=False, float_format="%.6f")
    trades.to_csv(output / "trades.csv", index=False, float_format="%.6f")

    # plot the same $10,000 starting value for both rules and buy-and-hold
    fig, ax = plt.subplots(figsize=(10, 5), layout="constrained")
    full_sample = equity.loc[equity["Period"] == "Full sample"]
    for strategy, values in full_sample.groupby("Strategy", sort=False):
        ax.plot(values["Date"], values["Portfolio_Value"], label=strategy)
    ax.set(
        title=f"AAPL backtest | {cost_bps:g} bps per fill",
        ylabel="Portfolio value (USD, log scale)",
        yscale="log",
    )
    ax.set_xlim(full_sample["Date"].min(), full_sample["Date"].max())
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.set_yticks([10_000, 20_000, 50_000, 100_000], ["$10k", "$20k", "$50k", "$100k"])
    ax.grid(axis="y", alpha=0.25)
    ax.legend(loc="upper left")
    fig.savefig(output / "equity_comparison.png", dpi=160)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description="Compare two systematic AAPL strategies.")
    parser.add_argument("--data", type=Path, default=DATA_PATH, help="Path to daily AAPL CSV")
    parser.add_argument("--cost-bps", type=float, default=10, help="Cost per trade side")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Results directory")
    args = parser.parse_args()
    if not isfinite(args.cost_bps) or not 0 <= args.cost_bps < 10000:
        parser.error("--cost-bps must be at least 0 and below 10000")
    if not args.data.is_file():
        parser.error("Market data missing. Run python -m utils.download_data first.")

    market_data = load_adjusted_data(args.data)
    metrics, equity, trades = run_study(market_data, args.cost_bps)
    save_results(metrics, equity, trades, args.output, args.cost_bps)

    # show the main metrics in the terminal and save the detailed tables above
    displayed = metrics.loc[metrics["Cost_bps"] == args.cost_bps, [
        "Period", "Strategy", "CAGR_pct", "Sharpe", "Max_Drawdown_pct", "Trades",
    ]]
    print(f"\nBACKTEST RESULTS | ${INITIAL_CASH:,} starting cash | {args.cost_bps:g} bps per fill")
    print(displayed.round(2).to_string(index=False))
    print(f"\nSaved results to {args.output}")


if __name__ == "__main__":
    main()
