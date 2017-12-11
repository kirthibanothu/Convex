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
import math

from convex.market_data import Playback

# Plotting
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as ticker

from convex.strategy_utils.utils import is_valid_book
from convex.strategy_utils.utils import simple_midpoint

import numpy as np

log = logbook.Logger('MD')


PlotValues = namedtuple("PlotValues", "ts bid ask realized_volitility")


class RealizedVolatility:
    def __init__(self, window_size):
        self._window_size = max(window_size/100, 100)
        self._historical = []
        self._counter = 0

    def add(self, book):
        midpoint = simple_midpoint(book)
        self._historical.append(math.log(midpoint))

        if len(self._historical) > self._window_size:
            self._historical.pop(0)

    def get(self, book):
        self._counter += 1
        if self._counter < 100:
            return None

        self._counter = 0
        self.add(book)

        returns = []
        prev_log_mp = self._historical[0]
        for log_mp in self._historical[1:]:
            returns.append(log_mp - prev_log_mp)

        real_vol = np.std(np.asarray(returns))
        return real_vol


def main(args):
    log.info('---------- Starting Signal Test ----------')

    if args['--input-file']:
        f = args['--input-file']

    realized_vol = RealizedVolatility(10000)

    plot = []

    num_updates = 0

    playback = Playback(f)
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

            if num_updates < 100:
                realized_vol.add(update['book'])
                continue

            real_vol = realized_vol.get(update['book'])
            if real_vol is None:
                continue

            plot.append(
                    PlotValues(
                        ts,
                        round(float(update['book']['bids'][0]['price']), 1),
                        round(float(update['book']['asks'][0]['price']), 1),
                        real_vol
                    )
            )

    time_stamps = np.asarray([x.ts for x in plot])
    bids = np.asarray([x.bid for x in plot])
    asks = np.asarray([x.ask for x in plot])

    real_vol = [x.realized_volitility for x in plot]
    min_val = min(bids)
    max_val = max(bids)
    max_real_vol = max(real_vol)

    norm_real_vol = [(float(i)/max_real_vol)*(max_val-min_val)+min_val for i in real_vol]

    real_vol = np.asarray(norm_real_vol)

    fig, ax = plt.subplots()

    ax.plot(time_stamps, bids, 'C2-',  # Green
            time_stamps, asks, 'C9-',  # Cyan
            time_stamps, real_vol, 'C0-')  # Blue

    yearsFmt = mdates.DateFormatter('%H:%M:%S')
    ax.xaxis.set_major_formatter(yearsFmt)

    ax.set_xlim(time_stamps[0], time_stamps[len(time_stamps)-1])

    fig.autofmt_xdate()
    ax.grid(True)

    plt.show()

    log.info('---------- Shutting down --------------\n\n\n\n\n\n')


if __name__ == '__main__':
    with logbook.FileHandler('../logs/signal.log',
                             level=logbook.INFO).applicationbound():
        args = docopt.docopt(__doc__)
        main(args)
