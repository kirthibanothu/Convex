#!/usr/bin/env python3
""" Aesop Strategy
Usage:
    ./aesop.py <backtest> <tune> <instrument>

"""
import asyncio
import datetime as dt
from decimal import Decimal
import time
import itertools
import docopt
import logbook
from pandas import DataFrame

from convex.common.instrument import instruments_lookup
from convex.market_data import Playback
from convex.common import Side, make_price, make_qty

# Strategy Utils
from convex.strategy_utils.basic_pnl_manager import BasicPnLManager
from convex.strategy_utils.utils import is_valid_book, simple_midpoint
from convex.signals.ema.dual_ema import DualEMA
from convex.backtest.backtest_trader import BacktestTrader

import datetime
from collections import namedtuple
import math


# Plotting
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from convex.strategy_utils.realized_volatility import RealizedVolatility

import numpy as np


log = logbook.Logger('Aesop')


PlotValues = namedtuple("PlotValues", "ts mkt realized_volitility")
StratValues = namedtuple("StratVales", "ts pnl")


class Aesop:
    def __init__(self, trader, pnl_manager, slow, fast):
        self._dual_ema = DualEMA(
            slow=slow, fast=fast, on_init_cb=None, on_signal_cb=self.on_signal)

        self._trader = trader
        self._pnl_manager = pnl_manager

        self._trader.add_event_handler(self._pnl_manager)
        self._last_buy_ts = None
        self._last_sell_ts = None

    async def on_signal(self, action, update):
        strp_time = update['timestamp'].split('.')[0].split('+')[0]
        curr_time = time.mktime(dt.datetime.strptime(
            strp_time,
            '%Y-%m-%d %H:%M:%S').timetuple())

        book = update['book']
        if action == 'BUY':
            if self._pnl_manager.get_cash_value() <= Decimal(1.00):
                return

            price = make_price(book['asks'][0]['price'])
            cash = self._pnl_manager.get_cash_value()
            qty = cash / price

            await self._trader.submit_order(
                side=Side.BID, price=price, qty=make_qty(Decimal(qty)),
                ioc=True, quote=True)
            self._last_buy_ts = curr_time
        else:
            if self._pnl_manager.get_crypto_value(book) <= Decimal(0.01):
                return

            price = make_price(book['bids'][0]['price'])
            qty = self._pnl_manager.crypto_coins

            await self._trader.submit_order(
                side=Side.ASK, price=price, qty=make_qty(Decimal(qty)),
                ioc=True, quote=True)
            self._last_sell_ts = curr_time

    async def initialize(self, update):
        if self._last_sell_ts is None:
            self._last_buy_ts = time.mktime(dt.datetime.strptime(
                update['timestamp'].split('.')[0],
                '%Y-%m-%d %H:%M:%S').timetuple())
            self._last_sell_ts = self._last_buy_ts

        await self._dual_ema.initialize(update)

    async def on_market_data(self, update):
        await self._dual_ema.on_market_data(update)


class StrategyHarness:
    def __init__(self, loop=None):
        if loop:
            self._loop = loop
        else:
            self._loop = asyncio.get_event_loop()

    async def run(self, params):
        pass

    async def run_against_params(self, params, files):
        realized_vol = RealizedVolatility(10000)

        plot = []

        num_updates = 0

        playback = Playback(files[0])
        for update in playback:
            num_updates += 1

            if is_valid_book(update['book']):
                timestamp = update['timestamp']
                if timestamp[-6:] == '+00:00':
                    timestamp = timestamp[:-6]

                ts = None
                try:
                    ts = datetime.datetime.strptime(
                            timestamp, '%Y-%m-%d %H:%M:%S.%f')
                except ValueError as e:
                    ts = datetime.datetime.strptime(
                            timestamp, '%Y-%m-%d %H:%M:%S')

                realized_vol.on_market_data(update['book'])
                if num_updates < 100:
                    continue
                
                real_vol = realized_vol.value
                if real_vol is None:
                    continue

                plot.append(
                        PlotValues(
                            ts,
                            round(float(simple_midpoint(update['book'])), 1),
                            real_vol
                        )
                )

        time_stamps = np.asarray([x.ts for x in plot])
        mkt = np.asarray([x.mkt for x in plot])
        y_anchor = Decimal(1000 - mkt[0])

        slow = [x for x in range(12*5, 20*5, 8*5)]
        fast = [x for x in range(2*5, 10*5, 8*5)]

        options = list(itertools.product(slow, fast))
        options = [x for x in options if x[0] > x[1]]

        log.info("parameter set [{}]: {}".format(len(options), options))

        fig, ax = plt.subplots()
        strat_plot = []

        colors = [
                'C0--', 'C1--', 'C2--', 'C3--', 'C4--',
                'C5--', 'C6--', 'C7--', 'C8--', 'C9--']

        for f in files:
            log.info("Using file: {}".format(f))

            for i in range(len(options)):
                strat_plot = await self.run_backtest(
                    params, f, options[i][0], options[i][1])

                first_ts = strat_plot[0]
                index = 0
                for i, p in enumerate(plot):
                    if p.ts == first_ts:
                        index = i
                        break

                shifted_mkt = mkt[index:]
                strat_time_stamps = np.asarray([x.ts for x in strat_plot])
                pnl = np.asarray([(x.pnl - (1000 - shifted_mkt[i])) for i, x in enumerate(strat_plot)])
                ax.plot(strat_time_stamps, pnl, colors[0], label=str(options[i]))

                print(strat_plot[len(strat_plot)-1])
                print(options[i])
                colors.pop(0)

        real_vol = [x.realized_volitility for x in plot]
        min_val = min(mkt)
        max_val = 370  # max(mkt)
        max_real_vol = max(real_vol)

        norm_real_vol = [(float(i)/max_real_vol)*(max_val-min_val)+min_val for i in real_vol]

        real_vol = np.asarray(norm_real_vol)

        ax.plot(time_stamps, mkt, 'C2-', label="Market")  # Green
        ax.plot(time_stamps, real_vol, 'C0-', label="RealVol")  # Blue

        plt.legend()

        yearsFmt = mdates.DateFormatter('%H:%M:%S')
        ax.xaxis.set_major_formatter(yearsFmt)

        ax.set_xlim(time_stamps[0], time_stamps[len(time_stamps)-1])

        fig.autofmt_xdate()
        ax.grid(True)

        plt.show()


    async def run_backtest(self, params, f, slow=22, fast=10):
        strat_values = []

        self._cash_value = 1000

        self._trader = BacktestTrader()
        self._pnl_manager = BasicPnLManager(
            get_balance_cb=None, broadcast_cb=None,
            crypto_coins=0, cash_value=self._cash_value, instrument={})

        self._strategy = Aesop(
                self._trader, self._pnl_manager, slow=slow, fast=fast)

        first_update = None

        playback = Playback(f)
        for update in playback:
            if self._strategy._dual_ema._init_processed is not -1:
                if first_update is None and is_valid_book(update['book']):
                    first_update = update
                await self._strategy.initialize(update)
            else:
                self._trader.on_market_data(update)
                await self._strategy.on_market_data(update)

                timestamp = update['timestamp']
                if timestamp[-6:] == '+00:00':
                    timestamp = timestamp[:-6]

                ts = None
                try:
                    ts = datetime.datetime.strptime(
                            timestamp, '%Y-%m-%d %H:%M:%S.%f')
                except ValueError as e:
                    ts = datetime.datetime.strptime(
                            timestamp, '%Y-%m-%d %H:%M:%S')

                strat_values.append(
                        StratValues(
                            ts,
                            (self._trader.get_strategy_value() +
                                self._trader._resting_order_sim.get_resting_value())
                            )
                )

        await self._trader.cancel_all()

        # Print final strategy value vs theoretical market value
        strategy_value, movement = await self._log_results(
                first_update, self._cash_value, slow, fast)

        # return strategy_value, movement
        return strat_values

    async def _log_results(self, first_update, cash_value, slow, fast):
        last_price = Decimal(self._trader.last_book.best_bid.price)
        first_price = Decimal(first_update['book']['bids'][0]['price'])
        movement = ((last_price-first_price)/first_price)*100
        if movement < 0:
            price_movement = "\033[1;31m"+str(movement)+"\033[0m"
        else:
            price_movement = "\033[1;32m"+str(movement)+"\033[0m"

        strategy_value = self._trader.get_strategy_value()
        if strategy_value < (cash_value+((movement/100)*cash_value)):
            strat_value = "\033[1;31m"+str(strategy_value)+"\033[0m"
        else:
            strat_value = "\033[1;32m"+str(strategy_value)+"\033[0m"

        log.info(
            'Strat Val: {}. Price diff: {}. Trades: {}. '
            'Fees: {}, Slow: {}. Fast: {}, Start: {}, End: {}, Spr: {}'.format(
                strat_value, price_movement,
                self._pnl_manager.num_trades,
                self._pnl_manager.total_fees,
                slow, fast, first_update['timestamp'], self._trader._last_ts,
                self._trader._at_min_spread))

        return strategy_value, movement


def main(args):
    log.info('Starting Aesop Strategy for {} in {} mode',
             args['<instrument>'], 'BACKTEST')

    instrument = instruments_lookup[args['<instrument>']]

    loop = asyncio.get_event_loop()
    strategy_harness = StrategyHarness(loop)

    params = {
                 'backtest': True if (args['<backtest>'] == "True") else False,
                 'tune': True if (args['<tune>'] == "True") else False,
                 'instrument': instrument
             }

    try:
        if params['backtest']:
            f = []
            f.append('recorder/20171117/ETH.json')

            if params['tune']:
                loop.run_until_complete(
                    strategy_harness.run_against_params(params, f))
            else:
                loop.run_until_complete(
                    strategy_harness.run_backtest(params, f[0]))
        else:
            loop.run_until_complete(strategy_harness.run(params))
    except KeyboardInterrupt:
        log.info('Keyboard Interrupt - Shutting down Aesop Strategy')

        # Cancel all running tasks
        for t in asyncio.Task.all_tasks():
            t.cancel()

        loop.run_forever()  # Wait for tasks to finish cleanup.

        # Gather exceptions.
        for t in asyncio.Task.all_tasks():
            try:
                t.exception()
            except Exception:
                log.exception('Exception during shutdown: {}', t)
    finally:
        loop.close()


if __name__ == '__main__':
    with logbook.FileHandler(
            'logs/mulit_aesop.log'.format(dt.datetime.today()),
            level=logbook.INFO).applicationbound():

        args = docopt.docopt(__doc__)
        main(args)
