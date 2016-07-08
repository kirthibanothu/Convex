#!/usr/bin/env python3 -m demos.demo_gdax

import asyncio

# from exchanges.gdax.market_data import Gateway as GdaxMdGateway
from exchanges.gdax.market_data_feed import Gateway as GdaxWsGateway


async def on_update(update):
    print('{}:\n{}'.format(update.instrument, update.book.show(5)))


def main():
    loop = asyncio.get_event_loop()
    # gw = GdaxMdGateway(loop=loop)
    gw = GdaxWsGateway(loop=loop)
    gw.register('BTC-USD', on_update)
    try:
        loop.run_until_complete(gw.launch())
    except KeyboardInterrupt:
        loop.stop()
        loop.close()

if __name__ == '__main__':
    main()
