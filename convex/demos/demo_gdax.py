#!/usr/bin/env python3 -m demos.demo_gdax

import asyncio
import signal

from logbook import TimedRotatingFileHandler

# from exchanges.gdax.market_data import Gateway as GdaxMdGateway
from exchanges.gdax.market_data_feed import Gateway as GdaxWsGateway


async def on_update(update):
    print('{}:\n{}'.format(update.instrument, update.book.show(5)))


def on_sigint(loop):
    print('Stopping')
    for task in asyncio.Task.all_tasks(loop=loop):
        task.cancel()


def main():
    loop = asyncio.get_event_loop()
    loop.add_signal_handler(signal.SIGINT, on_sigint, loop)

    # gw = GdaxMdGateway(loop=loop)
    gw = GdaxWsGateway(loop=loop)
    gw.register('BTC-USD', on_update)
    try:
        loop.run_until_complete(gw.launch())
    except asyncio.CancelledError:
        print('Tasks have been canceled')
    finally:
        loop.stop()
        loop.close()

log_fmt = \
        '[{record.time:%Y-%m-%d %H:%M:%S.%f}]' + \
        '[{record.level_name}] ' + \
        '{record.channel}: ' + \
        '{record.message}'

if __name__ == '__main__':
    log_handler = TimedRotatingFileHandler(
            'gdax_demo.log',
            format_string=log_fmt)
    with log_handler.applicationbound():
        main()
