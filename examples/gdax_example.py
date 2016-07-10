#!/usr/bin/env python3

from convex.common.app import AsyncApp

import convex.exchanges.gdax as gdax

async def on_update(update):
    print(('-' * 32) + '\n{}'.format(update.show(5)))


def main():
    app = AsyncApp(name='gdax_eaxmple')

    gw = gdax.MDGateway(loop=app.loop)
    gw.register('BTC-USD', on_update)

    app.run_loop(gw.launch())

if __name__ == '__main__':
    main()
