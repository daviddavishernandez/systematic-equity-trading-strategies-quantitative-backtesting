# this module will simulate the strategy day by day
# the backtester wont create the signals, it will excecute them
#logic: market data -> strategy creates signals -> backtester reads signals -> portfolio buys/sells -> portfolio value is recorded


from backtester.portfolio import Portfolio

class Backtester:
    def __init__(self, data, initial_cash=10000, cost_bps=0, fractional_shares=False): #stores the strategy data and creates a portfolio
        self.data = data.copy()
        self.portfolio = Portfolio(initial_cash, cost_bps, fractional_shares) # creates the portfolio that will execute the trades
        self.initial_cash = initial_cash
        self.cost_bps = cost_bps
        self.fractional_shares = fractional_shares

    def run(self, first_execution_signal=0): #run the backtest one row at a time
        # reset cash and holdings so repeated runs produce the same result
        self.portfolio = Portfolio(self.initial_cash, self.cost_bps, self.fractional_shares)
        if self.data.empty or not self.data["Signal"].isin([0, 1]).all():
            raise ValueError("The backtest needs at least one row and signals of 0 or 1")
        if first_execution_signal not in (0, 1):
            raise ValueError("The first execution signal must be 0 or 1")

        #shifting the signals:
        #move every signal forward by one row
        #ex: original signal
        # Day 1 -> 0
        # Day 2 -> 1
        # Day 3 -> 1

        #execution signal:
        # Day 1 -> 0
        # Day 2 -> 0
        # Day 3 -> 1

        # Therefore, Day 2's signal is executed on Day 3.
        # on the first row, use yesterday's signal from warm-up, or the default of 0
        self.data["Execution_Signal"] = self.data["Signal"].shift(
            1, fill_value=first_execution_signal
        )
        #fillna(0) means that after shifting, the first row will be N/A or Nan because there was no previous trading day
        #shift(1) basically just shifts the signals so theyre excecuted the next day
        # fill_value handles that empty first row directly and allows a prior warm-up signal.

        portfolio_values = [] # this list will store the value of the portfolio for every day in the dataset

        # record fills separately from target positions, including fees on both sides
        fees = []
        shares_held = []
        actions = []

        #go through the market data one day at a time:
        for _, row in self.data.iterrows():

            #represents the price when the next trading day begins
            execution_price = row["Open"]

            #signal created on the previous trading day
            execution_signal = row["Execution_Signal"]

            # current closing price to calculate worth of portfolio at the end of the day
            closing_price = row["Close"]

            fee = 0.0
            action = ""

            #buy:
            if (execution_signal == 1 and self.portfolio.shares == 0):
                fee = self.portfolio.buy(execution_price)
                if self.portfolio.shares > 0:
                    action = "BUY"

            #sell:
            elif (execution_signal == 0 and self.portfolio.shares > 0):
                fee = self.portfolio.sell(execution_price)
                action = "SELL"

            #calculate how much the portfolio is worth today
            total_value = self.portfolio.get_total_value(closing_price)

            #store that value in the list that we created in the beginning
            portfolio_values.append(total_value)
            fees.append(fee)
            shares_held.append(self.portfolio.shares)
            actions.append(action)

        # finally, we add the daily portfolio values to the DataFrame
        self.data["Portfolio_Value"] = portfolio_values
        self.data["Trade"] = actions
        self.data["Fee"] = fees
        self.data["Shares"] = shares_held
        return self.data.copy()
