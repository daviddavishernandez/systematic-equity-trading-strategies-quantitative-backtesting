"""Save the Yahoo Finance daily AAPL snapshot in the project's CSV format."""

import argparse
from datetime import datetime
import json
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

import pandas as pd

from utils.validator import DataValidator


# Jan 1, 2016 to Sep 1, 2026 (end exclusive). The extra history warms up the signals.
SOURCE_URL = (
    "https://query2.finance.yahoo.com/v8/finance/chart/AAPL"
    "?period1=1451606400&period2=1788220800&interval=1d"
)
DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "aapl_yahoo.csv"


def convert_snapshot(payload):
    # keep the source close and adjusted close so the adjustment can be checked later
    result = payload["chart"]["result"][0]
    if result["meta"]["symbol"] != "AAPL" or result["meta"]["currency"] != "USD":
        raise ValueError("Expected daily AAPL prices in USD")
    exchange_tz = ZoneInfo(result["meta"]["exchangeTimezoneName"])
    quotes = result["indicators"]["quote"][0]
    data = pd.DataFrame({
        "Date": [datetime.fromtimestamp(ts, exchange_tz).date() for ts in result["timestamp"]],
        "Open": quotes["open"],
        "High": quotes["high"],
        "Low": quotes["low"],
        "Close": quotes["close"],
        "Adj Close": result["indicators"]["adjclose"][0]["adjclose"],
        "Volume": quotes["volume"],
    })
    DataValidator(data).validate()
    if len(data) != 2680 or str(data["Date"].iloc[0]) != "2016-01-04" or str(
        data["Date"].iloc[-1]
    ) != "2026-08-31" or not data["Date"].is_monotonic_increasing:
        raise ValueError("The source did not return the expected 2,680 daily AAPL sessions")
    if not data["Adj Close"].between(0, float("inf"), inclusive="neither").all():
        raise ValueError("The source returned invalid adjusted closing prices")
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-json", type=Path, help="Use a saved Yahoo chart response")
    args = parser.parse_args()

    # either read the saved response or download the exact same study period
    try:
        if args.source_json:
            payload = json.loads(args.source_json.read_text())
        else:
            request = Request(SOURCE_URL, headers={"User-Agent": "Mozilla/5.0"})
            with urlopen(request, timeout=30) as response:
                payload = json.load(response)
        data = convert_snapshot(payload)
    except (OSError, URLError, KeyError, IndexError, TypeError, ValueError) as exc:
        parser.exit(1, f"Could not prepare AAPL data: {exc}\n")

    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    data.to_csv(DATA_PATH, index=False)
    print(f"Saved {len(data):,} daily rows to {DATA_PATH}")


if __name__ == "__main__":
    main()
