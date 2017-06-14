#!/usr/bin/env python3

import asyncio
import json
import logging
import os
import time

from convex.common.instrument import make_btc_usd, make_eth_usd, make_ltc_usd
from convex.exchanges import ExchangeID
from convex.market_data import Subscriber as MDSubscriber
from convex.exchanges import gdax

LOG_FORMAT = '%(asctime)s.%(msecs)03d: %(levelname)s | %(message)s | [%(module)s] [%(funcName)s]'
logging.basicConfig(format= LOG_FORMAT, datefmt='%Y-%m-%d %H:%M:%S', level=logging.INFO)

InstrumentsLookup = {
                        'BTC' : make_btc_usd(ExchangeID.GDAX),
                        'ETH' : make_eth_usd(ExchangeID.GDAX),
                        'LTC' : make_ltc_usd(ExchangeID.GDAX)
                    }

async def poll_subscriber(sub, feed_params):
    await asyncio.sleep(2)
    today = '{}.{}.{}'.format(time.strftime('%Y-%m-%d %H:%M:%S'), 'md', 'json')
    output_file = open('{}{}'.format(feed_params['output_dir'],
                                     today),
                       'a')
    while True:
        update = await sub.fetch()
        output_file.write(json.dumps(update.dump(feed_params['depth'])))
        await asyncio.sleep(feed_params['sleep_int'])

class Recorder:
    def __init__(self, loop=None):
        if loop:
            self.loop = loop
        else:
            self.loop = asynio.get_event_loop()

    async def launch_gw(self, gw):
        await gw.launch()
        await gw.request_shutdown()

    async def run(self, feed_params):
        gw = gdax.MDGateway(loop = self.loop)
        sub = MDSubscriber(InstrumentsLookup[feed_params['instrument']], gateway=gw)

        tasks = [
                    asyncio.ensure_future(
                        self.launch_gw(gw)
                    ),
                    asyncio.ensure_future(
                        poll_subscriber(sub, feed_params)
                    )
                ]
        self._future_tasks = asyncio.ensure_future(asyncio.gather(*tasks, loop=self.loop))

        try:
            await self._future_tasks
        except asyncio.CancelledError:
            pass

def main():
    feed_params = {
                      'depth': 10,
                      'sleep_int': 0.5,
                      'instrument': 'BTC',
                      'output_dir': 'data/'
                  }
    loop = asyncio.get_event_loop()

    recorder = Recorder(loop)
    loop.run_until_complete(recorder.run(feed_params))

if __name__ == '__main__':
    main() 
