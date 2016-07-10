#!/usr/bin/env python3

import asyncio

from convex.common.app import AsyncApp

from convex.market_data import Subscriber as MDSubscriber
import convex.exchanges.gdax as gdax


async def poll_subscriber(sub):
    while True:
        update = await sub.fetch()
        print(('-' * 32) + '\n{}'.format(update.show(5)))
        await asyncio.sleep(30)


def main():
    app = AsyncApp(name='gdax_example')

    gw = gdax.MDGateway(loop=app.loop)
    sub = MDSubscriber('BTC-USD', gateway=gw)

    app.run_loop(
            gw.launch(),
            poll_subscriber(sub))

if __name__ == '__main__':
    main()
