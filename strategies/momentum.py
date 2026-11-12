from strategies.strategy import Strategy


class MomentumStrategy(Strategy):
    """Own the stock when its trailing return is positive."""

    def __init__(self, data, lookback=63):
        super().__init__(data)

        # 63 trading days is roughly one quarter
        if lookback < 1:
            raise ValueError("Momentum lookback must be at least one trading day")
        self.lookback = lookback

    def generate_signals(self):
        strategy_data = self.data.copy()

        # compare today's close with the close 63 sessions earlier
        strategy_data["Momentum"] = strategy_data["Close"].pct_change(
            periods=self.lookback, fill_method=None
        )

        # stay in cash until the trailing return is available and positive
        strategy_data["Signal"] = (strategy_data["Momentum"] > 0).astype(int)
        return strategy_data
