#!/usr/bin/env python3 -m demos.demo_gdax

from logbook import TimedRotatingFileHandler

# from exchanges.gdax.market_data import Gateway as GdaxMdGateway
from exchanges.gdax.market_data_feed import Gateway as GdaxWsGateway

from common.app import AsyncApp

async def on_update(update):
    for trade in update.trades:
        print(trade)
    print('{}:\n{}'.format(update.instrument, update.book.show(0)))


def main():
    app = AsyncApp()

    # gw = GdaxMdGateway(loop=loop)
    gw = GdaxWsGateway(loop=app.loop)
    gw.register('BTC-USD', on_update)

    app.run_loop(gw.launch())

log_fmt = \
        '{record.time:%Y-%m-%d %H:%M:%S.%f} - ' + \
        '{record.module} - ' + \
        '{record.level_name} - ' + \
        '{record.message}'

if __name__ == '__main__':
    log_handler = TimedRotatingFileHandler(
            'gdax_demo.log',
            format_string=log_fmt)
    with log_handler.applicationbound():
        main()
