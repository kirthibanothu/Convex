#!/usr/bin/env python3

import asyncio

from convex.common.app import AsyncApp
from convex.common.instrument import make_btc_usd
from convex.exchanges import ExchangeID

from convex.market_data import Subscriber as MDSubscriber
from convex.exchanges import gdax


async def poll_subscriber(sub):
    while True:
        update = await sub.fetch()
        print(('-' * 32) + '\n{}'.format(update.show(5)))
        await asyncio.sleep(10)


def main():
    app = AsyncApp(name='gdax_example')

    gw = gdax.MDGateway(loop=app.loop)
    sub = MDSubscriber(make_btc_usd(ExchangeID.GDAX), gateway=gw)

    app.add_run_callback(gw.launch,
                         shutdown_cb=gw.request_shutdown)
    app.add_run_callback(poll_subscriber(sub))

    app.run()

if __name__ == '__main__':
    main()
