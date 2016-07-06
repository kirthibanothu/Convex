#!/usr/bin/env python3 -m demos.demo_gdax

import asyncio

from exchanges.gdax.market_data import Gateway as GdaxMdGateway


async def on_update(update):
    print('{}: {}'.format(update.instrument, update.book))


def main():
    loop = asyncio.get_event_loop()
    gw = GdaxMdGateway(loop=loop)
    gw.register('BTC-USD', on_update)
    try:
        loop.run_until_complete(gw.launch())
    except KeyboardInterrupt:
        loop.close()

if __name__ == '__main__':
    main()
