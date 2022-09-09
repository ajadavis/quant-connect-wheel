# region imports
from AlgorithmImports import *
# endregion
# copied From:  https://www.quantconnect.com/terminal/processCache/?request=embedded_backtest_995782f9a954f9acdabe27351860ad22.html

from QuantConnect.Securities.Option import OptionPriceModels
from datetime import timedelta
import decimal as d


class CoveredCallAlgorithm(QCAlgorithm):

    def Initialize(self):
        # no of strikes around ATM => for uniform selection (equal # above & below)
        self._no_K = 20
        # min num of days to expiration => for uniform selection (equal # above & below)
        self.MIN_EXPIRY = 1
        # max num of days to expiration => for uniform selection (equal # above & below)
        self.MAX_EXPIRY = 4
        self.MAX_DELTA = d.Decimal(0.3)  # quantconnect parameter for Delta
        # what's the minimum premium you'll accept to buy an option
        self.MIN_PREMIUM = d.Decimal(0.3)
        self.ticker = "SPY"
        self.benchmarkTicker = "SPY"
        self.SetStartDate(2013, 1, 1)
        self.SetEndDate(2014, 12, 1)
        self.SetCash(50000)

        # ???Figure out how to set it to weekly???
        # ???Open on 1st day trading, end on Friday or Last Day
        # ???Figure out how to set it to start 1 hour after market opens??
        # ?Specify number of options to buy??

        self.resolution = Resolution.Daily
        self.call, self.put, self.takeProfitTicket = None, None, None

        equity = self.AddEquity(self.ticker, self.resolution)
        option = self.AddOption(self.ticker, self.resolution)
        self.symbol = option.Symbol

        # set strike/expiry filter for this option chain
        # option.SetFilter(-3, +3, timedelta(30), timedelta(60))

        # set our strike/expiry filter for this option chain
        option.SetFilter(self.UniverseFunc)

        # for greeks and pricer (needs some warmup) - https://github.com/QuantConnect/Lean/blob/21cd972e99f70f007ce689bdaeeafe3cb4ea9c77/Common/Securities/Option/OptionPriceModels.cs#L81
        # both European & American, automatically
        option.PriceModel = OptionPriceModels.CrankNicolsonFD()

        # this is needed for Greeks calcs
        self.SetWarmUp(TimeSpan.FromDays(60))    # timedelta(7)

        # use the underlying equity as the benchmark
        # self.SetBenchmark(self.benchmarkTicker)
        self.SetBenchmark(self.benchmarkTicker)

    def OnData(self, slice):
        if (self.IsWarmingUp):
            return

        option_invested = [
            x.Key for x in self.Portfolio if x.Value.Invested and x.Value.Type == SecurityType.Option]

        if len(option_invested) == 1:
            return

        # If we already have underlying - check if we need to sell covered call
        if self.Portfolio[self.ticker].Invested:
            self.TradeCallOption(slice)
        else:
            self.TradePutOption(slice)

    def TradePutOption(self, slice):
        for i in slice.OptionChains:
            if i.Key != self.symbol:
                continue

            chain = i.Value

            # filter the put options contracts
            puts = [x for x in chain if x.Right == OptionRight.Put and abs(x.Greeks.Delta) > 0 and abs(
                x.Greeks.Delta) < self.MAX_DELTA and x.BidPrice > self.MIN_PREMIUM]

            # sorted the contracts according to their expiration dates and choose the ATM options
            contracts = sorted(sorted(puts, key=lambda x: x.BidPrice, reverse=True),
                               key=lambda x: x.Expiry)

            if len(contracts) == 0:
                continue

            self.put = contracts[0].Symbol

            # short the call options
            ticket = self.MarketOrder(self.put, -1, asynchronous=False)

            # set Take Profit order
            self.takeProfitTicket = self.LimitOrder(self.put, 1, round(
                float(ticket.AverageFillPrice) * float(d.Decimal(0.5)), 2))

    def TradeCallOption(self, slice):
        for i in slice.OptionChains:
            if i.Key != self.symbol:
                continue

            chain = i.Value

            # filter the put options contracts
            calls = [x for x in chain if x.Right == OptionRight.Call and abs(x.Greeks.Delta) > 0 and abs(
                x.Greeks.Delta) < self.MAX_DELTA and x.BidPrice > self.MIN_PREMIUM]

            # sorted the contracts according to their expiration dates and choose the ATM options
            contracts = sorted(sorted(calls, key=lambda x: x.BidPrice, reverse=True),
                               key=lambda x: x.Expiry)

            if len(contracts) == 0:
                continue

            self.call = contracts[0].Symbol

            # short the call options
            ticket = self.MarketOrder(self.call, -1, asynchronous=False)

            # set Take Profit order
            self.takeProfitTicket = self.LimitOrder(self.call, 1, round(
                float(ticket.AverageFillPrice) * float(d.Decimal(0.5)), 2))

    def OnOrderEvent(self, orderEvent):
        self.Log(str(orderEvent))

    def OnAssignmentOrderEvent(self, assignmentEvent):
        if self.takeProfitTicket != None:
            self.takeProfitTicket.cancel()
            self.takeProfitTicket = None

    def UniverseFunc(self, universe):
        return universe.IncludeWeeklys()\
            .Strikes(-self._no_K, self._no_K)\
            .Expiration(timedelta(self.MIN_EXPIRY), timedelta(self.MAX_EXPIRY))

    def OnFrameworkData(self):
        return
