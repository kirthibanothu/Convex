#!/usr/bin/env python3
"""EMA test signal

Usage:
    ./ema.py [options]

Options:
    -i --input-file <input-file> Input file
"""

import logbook
import docopt
import datetime
from collections import namedtuple

from convex.market_data import Playback

# Plotting
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

import numpy as np

log = logbook.Logger('MD')


MAX_UPDATES_TO_PROCESS = 25800


BookLevel = namedtuple('BookLevel', ['bid', 'ask', 'mid_price'])


def simple_midpoint(book):
    bid = book['bids'][0]
    ask = book['asks'][0]
    total_qty = float(bid['qty'])+float(ask['qty'])

    weighted_bid = float(bid['price'])*float(ask['qty'])
    weighted_ask = float(ask['price'])*float(bid['qty'])
    return (weighted_bid + weighted_ask) / total_qty


class EMATracker:
    def __init__(self, periods, value):
        self._value = value
        self._multiplier = (2/(periods + 1))

    @property
    def value(self):
        return self._value

    def _compute_ema(self, price, prev):
        return (price - prev)*self._multiplier + prev

    def _compute_dema(self, price, ema):
        return (2*ema)-(self._compute_ema(price, ema))

    def on_price(self, price):
        ema = self._compute_ema(price, self._value)
        # self._value = ema
        self._value = self._compute_dema(price, ema)
        # self._value = (price - self._value)*self._multiplier + self._value
        return self._value


def is_valid_book(book):
    return len(book['asks']) > 0 and len(book['bids']) > 0


class DualEMA:
    def __init__(self, slow, fast, on_signal_cb=None, updates=None):
        slow_value = 0.0
        fast_value = 0.0
        fastest_value = 0.0

        fastest = 5

        curr_sum = 0.0
        processed = 0
        for update in updates:
            if is_valid_book(update['book']):
                processed += 1

                curr_sum += simple_midpoint(update['book'])
                if processed == fastest:
                    fastest_value = curr_sum / fastest
                if processed == fast:
                    fast_value = curr_sum / fast
                if processed == slow:
                    slow_value = curr_sum / slow
                    break

        self._slow = EMATracker(slow, slow_value)
        self._fast = EMATracker(fast, fast_value)
        self._fastest = EMATracker(fastest, fastest_value)

        self._action = 'BUY' if (fast_value > slow_value) else 'SELL'
        self._mkt_price = 0.0

        self._on_signal_cb = on_signal_cb

    @property
    def action(self):
        return self._action

    @property
    def mkt_price(self):
        return self._mkt_price

    def on_market_data(self, update):
        self._mkt_price = simple_midpoint(update['book'])

        slow = self._slow.on_price(self._mkt_price)
        fast = self._fast.on_price(self._mkt_price)
        self._fastest.on_price(self._mkt_price)

        if self._action == 'BUY':
            if fast < slow:
                self._action = 'SELL'
                if self._on_signal_cb:
                    self._on_signal_cb(self._action)
        else:
            if fast > slow:
                self._action = 'BUY'
                if self._on_signal_cb:
                    self._on_signal_cb(self._action)

    def get_prices(self):
        return (self._slow.value, self._fast.value, self._fastest.value)


def top_of_book(update):
    if len(update['book']['asks']) > 0 and len(update['book']['bids']) > 0:
        bid = update['book']['asks'][0]
        ask = update['book']['bids'][0]
        log.info('{} - {} | {} - {}'.format(
                bid['qty'], bid['price'], ask['price'], ask['qty']))


def compute_pnl(init_action, prices):
    trade_prices = []

    # This is inverted logic - since the first action we take
    # is the opposite of the init action
    should_buy = True if init_action == 'SELL' else False
    fees = 0.025/100
    # fees = 0.0

    '''
    cash = 0.0 if should_buy else 100.0
    coins = (100/trade_values[0]) if should_buy else 0
    '''
    cash = 100.0 if should_buy else 0.0
    coins = 0.0 if should_buy else (100/prices[0].ask)

    previous = 100
    for val in prices:
        if should_buy:
            # BUY
            coins = (cash-(cash*fees))/float(val.ask)
            cash = 0.0
            after = cash + (coins*val.ask)
            log.info(
                'BUY at {}. previous: {}. after: {}. PNL: {}'.format(
                    val.ask, previous, after, round(after - previous, 8)))

            previous = after
            trade_prices.append(val.ask)
        else:
            # SELL
            cash = val.bid*coins - (val.bid*coins*fees)
            coins = 0.0
            after = cash + (coins*val.bid)
            log.info(
                'SELL at {}. previous: {}. after: {}. PNL: {}'.format(
                    val.bid, previous, after, round(after - previous, 8)))

            previous = after
            trade_prices.append(val.bid)

        should_buy = not should_buy

    return (cash + coins*prices[len(prices) - 1].mid_price, trade_prices)


def main(args):
    # f = '../recorder/20170928_144839_BTCUSD@GDAX.json'
    # f = '../recorder/20170928_144752_LTCUSD@GDAX.json'
    # f = '../recorder/20171014_202537_BTCUSD@GDAX.json'
    # f = '../recorder/20171015_145012_LTCUSD@GDAX.json'
    # f = '../recorder/20171015_145011_BTCUSD@GDAX.json'
    # f = '../recorder/20171020_033216_ETHUSD@GDAX.json'
    # f = '../recorder/LTC.json'
    # f = '../recorder/ETH.json'
    # f = '../recorder/BTC.json'
    # f = '../recorder/20171015_145010_ETHUSD@GDAX.json'
    # f = '../recorder/20170928_144812_ETHUSD@GDAX.json'
    # f = '../recorder/20171014_183313_BTCUSD@GDAX.json'
    if args['--input-file']:
        f = args['--input-file']

    playback = Playback(f)

    log.info('---------- Starting Signal Test ----------')

    dual_ema = DualEMA(slow=140, fast=20, updates=playback)

    plot = []

    updates_processed = 0

    tracked_action = dual_ema.action
    init_action = tracked_action

    playback = Playback(f)
    for update in playback:
        if is_valid_book(update['book']):
            updates_processed += 1
            '''
            if updates_processed == MAX_UPDATES_TO_PROCESS:
                break
            '''
            if updates_processed < 50:
                continue

            dual_ema.on_market_data(update)

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

            book_level = BookLevel(0, 0, 0)
            # marker = 0
            if dual_ema.action != tracked_action:
                # marker
                book_level = BookLevel(
                        float(update['book']['bids'][0]['price']),
                        float(update['book']['asks'][0]['price']),
                        float(simple_midpoint(update['book'])))

                tracked_action = dual_ema.action

            plot.append(
                (ts,
                 dual_ema.get_prices()[0],
                 dual_ema.get_prices()[1],
                 dual_ema.get_prices()[2],
                 dual_ema.mkt_price,
                 book_level))

    values = np.asarray([x[0] for x in plot])
    slow_emas = np.asarray([x[1] for x in plot])
    fast_emas = np.asarray([x[2] for x in plot])
    fastest_emas = np.asarray([x[3] for x in plot])
    mid_points = np.asarray([x[4] for x in plot])
    prices = [x[5] for x in plot if x[5].bid != 0]
    trade_values = np.asarray(
        [x[0] for x in plot if (x[5].bid != 0 or x[5].ask != 0)])

    pnl, trade_prices = compute_pnl(init_action, prices)

    first = prices[0].mid_price
    last = prices[len(prices) - 1].mid_price

    log.info('Trades: {}. PnL: {}. Price Movement: {}'.format(
        len(trade_values), pnl, ((last - first)/first)*100))

    fig, ax = plt.subplots()

    ax.plot(values, mid_points, 'C7-',  # Grey
            values, fastest_emas, 'C9-',  # Cyan
            values, fast_emas, 'C0-',  # Blue
            values, slow_emas, 'C2-',  # Green
            trade_values, trade_prices, 'r.')

    yearsFmt = mdates.DateFormatter('%H:%M:%S')
    ax.xaxis.set_major_formatter(yearsFmt)

    ax.set_xlim(values[0], values[len(values)-1])

    fig.autofmt_xdate()
    ax.grid(True)
    plt.show()

    log.info('---------- Shutting down --------------\n\n\n\n\n\n')


if __name__ == '__main__':
    with logbook.FileHandler('../logs/signal.log',
                             level=logbook.INFO).applicationbound():
        args = docopt.docopt(__doc__)
        main(args)
