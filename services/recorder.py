#!/usr/bin/env python3
"""GDAX Market Data Recorder

Usage:
    ./recorder.py <INSTRUMENT> <DEPTH> <SLEEP_INT> <OUTPUT_DIR>
"""

import asyncio
import docopt
import json
import logbook
import logging
import os
import time

from convex.common.instrument import instruments_lookup
from convex.common.utils.conversions import humanize_bytes
from convex.market_data import Subscriber as MDSubscriber
from convex.exchanges import gdax

log = logbook.Logger('EXAMPLE')

LOG_FORMAT = '%(asctime)s.%(msecs)03d: %(levelname)s | %(message)s | [%(module)s] [%(funcName)s]'
logging.basicConfig(format= LOG_FORMAT, datefmt='%Y-%m-%d %H:%M:%S', level=logging.INFO)

async def poll_subscriber(sub, filename, feed_params):
    await asyncio.sleep(2)

    output_file = open(filename, 'a')

    logging.info("Writing output to file: {}".format(filename))

    while True:
        update = await sub.fetch()
        output_file.write(json.dumps(update.dump(feed_params['depth']))+'\n')
        await asyncio.sleep(feed_params['sleep_int'])

async def file_watcher(filename):
    await asyncio.sleep(5)

    while True:
        size_mb = humanize_bytes(os.path.getsize(filename))

        logging.info("File Size: {}".format(size_mb))
        await asyncio.sleep(60)

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
        sub = MDSubscriber(instruments_lookup[feed_params['instrument']], gateway=gw)

        today = '{}.{}.{}'.format(time.strftime('%Y-%m-%d %H:%M:%S'), 'md', 'json')
        filename = '{}{}-{}'.format(feed_params['output_dir'], feed_params['instrument'], today)

        tasks = [
                    asyncio.ensure_future(
                        self.launch_gw(gw)
                    ),
                    asyncio.ensure_future(
                        poll_subscriber(sub, filename, feed_params)
                    ),
                    asyncio.ensure_future(
                        file_watcher(filename)
                    )
                ]
        self._future_tasks = asyncio.ensure_future(asyncio.gather(*tasks, loop=self.loop))

        try:
            await self._future_tasks
        except asyncio.CancelledError:
            pass

def main(args):
    feed_params = {
                      'depth': int(args['<DEPTH>']),
                      'sleep_int': float(args['<SLEEP_INT>']),
                      'instrument': args['<INSTRUMENT>'],
                      'output_dir': args['<OUTPUT_DIR>']
                  }
    logging.info("Starting Market Data Recorder for {}".format(feed_params['instrument']))
    logging.info("Params: {}".format(feed_params))

    loop = asyncio.get_event_loop()

    recorder = Recorder(loop)
    loop.run_until_complete(recorder.run(feed_params))

if __name__ == '__main__':
    args = docopt.docopt(__doc__)
    main(args)
