# Market Data
This will only be taken into account to keep track of the markets we have in the program.
Specifically, this folder stores historical market data used by the backtesting framework.

The original data source was listed as Stooq (daily historical prices).

- `apple.csv` is the original 22-row CSV retained as a test fixture. It contains a gap from January to July 2026.
- `aapl_yahoo.csv` is the research input from [Yahoo Finance AAPL historical prices](https://finance.yahoo.com/quote/AAPL/history/). The ZIP contains the snapshot used for the reported results. Git ignores this file so the public repo can use the download command in the main README.

The snapshot contains 2,680 AAPL sessions in USD from January 4, 2016 to August 31, 2026. The study uses 2,512 sessions from September 1, 2016 to August 31, 2026. Earlier observations initialize the two indicators. The CSV stores the source open, high, low, close, adjusted close and volume.

The snapshot was retrieved November 12, 2026. Its SHA-256 is `79e4e73acb70d33daa80fa41c4081e6b8bf021a159f4e6b81a7221fb8abc9c17`. Provider revisions and subsequent corporate-action adjustments may change future downloads.
