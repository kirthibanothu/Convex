#!/usr/bin/env python3
"""GDAX Market Data Recorder

Usage:
    ./recorder.py [options] <instrument>

Options:
    -f --format <format>            Output format [default: json].
    -n --interval <write-interval>  Seconds betwen each write [default: 1.0].
    -o --output <outdir>            Seconds betwen each write.
    -d --depth <depth>              Number of levels to record [default: 10].

Arguments:
    format  File format (json, msgpack).
"""

import asyncio
import os
import json
import datetime as dt

import docopt
import logbook
import msgpack

from convex.common.instrument import instruments_lookup
from convex.common.utils.conversions import humanize_bytes
from convex.market_data import Subscriber as MDSubscriber
from convex.exchanges import gdax

log = logbook.Logger('MD')


class Recorder:
    def __init__(self,
                 instrument,
                 depth, *,
                 output_dir='.',
                 interval=3,
                 fmt='json',
                 loop=None):
        self._loop = (loop if loop is not None
                      else asyncio.get_event_loop())
        self._gateway = gdax.MDGateway(loop=self._loop)
        self._subscriber = MDSubscriber(instrument, gateway=self._gateway)
        self._tasks = []

        if fmt == 'json':
            file_ext = 'json'
            file_flags = 'a'
            self._write_update = self._write_json
        elif fmt == 'msgpack':
            file_ext = 'mp'
            file_flags = 'ab'
            self._write_update = self._write_msgpack
            self._packer = msgpack.Packer()
        else:
            raise ValueError('Unsupported format: {}'.format(fmt))

        today = dt.datetime.utcnow()
        filename = '{:%Y%m%d}_{}.{}'.format(today, instrument, file_ext)
        output_dir = os.path.expanduser(output_dir)
        self._filename = os.path.join(output_dir, filename)
        self._file = open(self._filename, file_flags)
        log.info('Writing output to {}', self._filename)

        self._interval = max(interval, 0.001)
        self._depth = max(depth, 1)

    async def run(self):
        coros = [
            self._gateway.launch(),
            self._poll_subscriber(),
        ]
        try:
            await asyncio.gather(*coros, loop=self._loop)
        except asyncio.CancelledError:
            pass
        finally:
            await self._gateway.request_shutdown()
            self._file.close()

    async def _poll_subscriber(self):
        self._watch_file()
        try:
            while True:
                update = await self._subscriber.fetch()
                self._write_update(update)
                await asyncio.sleep(self._interval)
        except asyncio.CancelledError:
            pass

    def _write_msgpack(self, update):
        data = update.dump(depth=self._depth)
        msgpack.pack(data, self._file)

    def _write_json(self, update):
        json.dump(update.dump(depth=self._depth), self._file)
        self._file.write('\n')

    def _write_update(self, update):
        """Write update to file"""
        raise RuntimeError('Should be replaced by '
                           '_write_json or _write_msgpack')

    def _watch_file(self, interval=60):
        """Log file size periodically."""
        file_size = humanize_bytes(os.path.getsize(self._filename))
        log.info('File Size: {}', file_size)
        self._loop.call_later(interval, self._watch_file)


def main(args):
    log.info('Starting Market Data Recorder for {}', args['<instrument>'])

    loop = asyncio.get_event_loop()

    instrument = instruments_lookup[args['<instrument>']]

    recorder = Recorder(instrument,
                        depth=int(args['--depth']),
                        interval=float(args['--interval']),
                        fmt=args['--format'],
                        loop=loop)

    task = asyncio.ensure_future(recorder.run(), loop=loop)
    try:
        loop.run_until_complete(task)
    except KeyboardInterrupt:
        # Cancel all running tasks.
        for t in asyncio.Task.all_tasks():
            t.cancel()

        loop.run_forever()  # Wait for tasks to finish cleanup.

        # Gather exceptions.
        for t in asyncio.Task.all_tasks():
            try:
                t.exception()
            except Exception:
                log.exception('Exception during shutdown: {}', t)
    finally:
        loop.close()


if __name__ == '__main__':
    with logbook.FileHandler('recorder.log',
                             level=logbook.INFO).applicationbound():
        args = docopt.docopt(__doc__)
        main(args)
