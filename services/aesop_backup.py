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
import numpy

from convex.common.instrument import instruments_lookup
from convex.market_data import Playback
from convex.common import Side, make_price, make_qty

# Strategy Utils
from convex.strategy_utils.basic_pnl_manager import BasicPnLManager
from convex.strategy_utils.utils import is_valid_book
from convex.signals.ema.dual_ema import DualEMA
from convex.backtest.backtest_trader import BacktestTrader


log = logbook.Logger('Aesop')


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
        # log.info('OnSignal TS: {}. Action: {}. Mkt Price: {}'.format(
        #     update['timestamp'], action, simple_midpoint(update['book'])))
        strp_time = update['timestamp'].split('.')[0].split('+')[0]
        curr_time = time.mktime(dt.datetime.strptime(
            strp_time,
            '%Y-%m-%d %H:%M:%S').timetuple())

        book = update['book']
        # PERIOD = 1
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
        # slow = [5, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        # fast = [1,  5, 10, 20, 30, 40, 50, 60, 70, 80, 90]
        slow = [x for x in range(20*5, 40*5, 4*5)]
        fast = [x for x in range(2*5, 22*5, 4*5)]

        options = list(itertools.product(slow, fast))
        options = [x for x in options if x[0] > x[1]]

        log.info("parameter set [{}]: {}".format(len(options), options))

        top_ten_batches = []
        for f in files:
            log.info("Using file: {}".format(f))
            two_d = [[0 for i in range(len(fast))] for j in range(len(slow))]

            log.info('DataFrame: \n{}'.format(DataFrame(two_d).to_string()))
            for i in range(len(options)):
                strategy_value, movement = await self.run_backtest(
                    params, f, options[i][0], options[i][1])
                slow_index = slow.index(options[i][0])
                fast_index = fast.index(options[i][1])
                pnl_perc = (
                    ((strategy_value-self._cash_value)/self._cash_value)*100)
                two_d[slow_index][fast_index] = Decimal(pnl_perc)-movement

            log.info('\n{}'.format(DataFrame(two_d).to_string()))

            # Print top 10 performing indices
            i = (-numpy.asarray(two_d)).argsort(axis=None, kind='mergesort')
            j = numpy.unravel_index(i, numpy.asarray(two_d).shape)
            top_ten = numpy.vstack(j).T[:20:1]
            ranked = []
            for x in top_ten:
                if two_d[x[0]][x[1]] != 0:
                    ranked.append([slow[x[0]], fast[x[1]]])

            top_ten_batches.append(ranked)

            log.info('arr: {}\n'.format(ranked))

        log.info(
            'Top Ranked Batches : \n{}'.format(
                DataFrame(top_ten_batches).to_string()))

        runoff = {}
        for batch in top_ten_batches:
            for value in batch:
                runoff[', '.join(str(e) for e in value)] = 0

        log.info("Computing runoff values")
        # Compute runoff
        for batch in top_ten_batches:
            i = 20
            for value in batch:
                runoff[', '.join(str(e) for e in value)] = runoff[', '.join(str(e) for e in value)] + i
                i -= 1
        
        log.info("runoff map {}".format(runoff))
        vals = [(k, runoff[k]) for k in sorted(runoff, key=runoff.get, reverse=True)]
        log.info('Runoff values: \n{}'.format(vals))

    async def run_backtest(self, params, f, slow=22, fast=10):
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

        await self._trader.cancel_all()

        # Print final strategy value vs theoretical market value
        strategy_value, movement = await self._log_results(
                first_update, self._cash_value, slow, fast)

        return strategy_value, movement

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
            '''
		[('28, 2', 214), ('36, 2', 207), ('20, 2', 192), ('32, 2', 190), ('24, 6', 161), ('24, 2', 155), ('28, 10', 143), ('20, 14', 142), ('32, 6', 139), ('28, 6', 138), ('24, 10', 128), ('24, 18', 127), ('20, 6', 122), ('36, 14', 120), ('28, 14', 113), ('20, 18', 111), ('20, 10', 107), ('32, 18', 98), ('24, 14', 95), ('32, 10', 92), ('36, 6', 83), ('36, 10', 76), ('36, 18', 75), ('32, 14', 65), ('28, 18', 57)]

            '''
            '''
            f.append('recorder/20171114_011925_ETHUSD@GDAX.json')
            f.append('recorder/20171114_011925_LTCUSD@GDAX.json')
            f.append('recorder/20171114_011926_BTCUSD@GDAX.json')
            '''
            '''
            f.append('recorder/20171115_031727_ETHUSD@GDAX.json')
            f.append('recorder/20171115_031729_LTCUSD@GDAX.json')
            f.append('recorder/20171115_031729_BTCUSD@GDAX.json')
	    '''
            f.append('recorder/20171117/ETH.json')
            '''
            f.append('recorder/20171116/LTC.json')
            f.append('recorder/20171116/ETH.json')
            f.append('recorder/20171116/BTC.json')
            '''
            '''
            f.append('recorder/20170928_144839_BTCUSD@GDAX.json')
            f.append('recorder/20170928_144752_LTCUSD@GDAX.json')
            f.append('recorder/20171014_202537_BTCUSD@GDAX.json')
            f.append('recorder/20171015_145012_LTCUSD@GDAX.json')
            f.append('recorder/20171015_145011_BTCUSD@GDAX.json')
            f.append('recorder/20171015_145010_ETHUSD@GDAX.json')
            f.append('recorder/20170928_144812_ETHUSD@GDAX.json')
            f.append('recorder/20171014_183313_BTCUSD@GDAX.json')
            f.append('recorder/20171020_033216_ETHUSD@GDAX.json')
            f.append('recorder/LTC.json')
            f.append('recorder/ETH.json')
            f.append('recorder/BTC.json')
            '''

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
    '''
    with logbook.FileHandler(
            'logs/aesop_{:%Y%m%d_%H:%M:%S}.log'.format(dt.datetime.today()),
            level=logbook.INFO).applicationbound():
    '''
    with logbook.FileHandler(
            'logs/aesop.log'.format(dt.datetime.today()),
            level=logbook.INFO).applicationbound():

        args = docopt.docopt(__doc__)
        main(args)
