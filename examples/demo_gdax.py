#!/usr/bin/env python3

from convex.common.app import AsyncApp

# from exchanges.gdax.market_data import Gateway as GdaxMdGateway
from convex.exchanges.gdax.market_data_feed import Gateway as GdaxWsGateway

async def on_update(update):
    print(update.show(5))


def main():
    app = AsyncApp(name='gdax_demo')

    # gw = GdaxMdGateway(loop=loop)
    gw = GdaxWsGateway(loop=app.loop)
    gw.register('BTC-USD', on_update)

    app.run_loop(gw.launch())

if __name__ == '__main__':
    main()
