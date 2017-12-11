#!/usr/bin/env python3
"""GDAX Market Data Recorder

Usage:
    ./recorder.py [options] <instrument>

Options:
    -f --format <format>            Output format [default: json].
    -n --interval <write-interval>  Seconds betwen each write [default: 1.0].
    -o --output <path>              Output directory [default: ./].
    -d --depth <depth>              Number of levels to record [default: 10].
    -m --maxsize <filesize>         File size before rolloer [default: 512MB].

Arguments:
    format  File format (json, msgpack).
"""

import asyncio
import datetime as dt
import gzip
import json
import os
import shutil
import time

import docopt
import logbook
import msgpack

from convex.common.instrument import instruments_lookup
from convex.common.utils import humanize_bytes, dehumanize_bytes
from convex.market_data import Subscriber as MDSubscriber
from convex.exchanges import gdax

log = logbook.Logger('MD')


class Recorder:
    def __init__(self,
                 instrument,
                 depth: int,
                 output_dir: str,
                 interval: float,
                 fmt: str,
                 maxfilesize: int, *,
                 loop=None):
        if maxfilesize <= 1024:
            raise ValueError('maxsize must be greater than 1KB')

        self._loop = (loop if loop is not None
                      else asyncio.get_event_loop())
        self._gateway = gdax.MDGateway(loop=self._loop)
        self._subscriber = MDSubscriber(instrument, gateway=self._gateway)
        self._tasks = []

        self._interval = max(interval, 0.001)
        self._depth = max(depth, 1)
        self._maxfilesize = maxfilesize
        if fmt == 'json':
            self._write_update = self._write_json
        elif fmt == 'msgpack':
            self._write_update = self._write_msgpack
        else:
            raise ValueError('Unsupported format: {}'.format(fmt))

        self._output_dir = os.path.expanduser(output_dir)
        self._rollover_file()

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
            self.cleanup()

    def _cleanup(self):
        self._file.close()
        filename, proc_time = self._gzip_file(self._filename)
        log.info('gzipped file {} took {:0.2f}s', filename, proc_time)

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
        file_size = os.path.getsize(self._filename)
        log.info('Output file size: {}, {}',
                 humanize_bytes(file_size),
                 self._filename)
        if file_size >= self._maxfilesize:
            self._rollover_file()
        self._loop.call_later(interval, self._watch_file)

    def _rollover_file(self):
        try:
            self._file.close()  # Close file if one is open.
        except AttributeError:
            pass
        else:
            self._sched_gzip()  # gzip file on seperate thread.

        today = dt.datetime.utcnow()
        instrument = self._subscriber.instrument
        file_ext, flags = {
            self._write_json: ('json', 'a'),
            self._write_msgpack: ('mp', 'ab'),
        }[self._write_update]

        filename = '{:%Y%m%d_%H%M%S}_{}.{}'.format(today, instrument, file_ext)
        self._filename = os.path.join(self._output_dir, filename)
        self._file = open(self._filename, flags)
        log.info('Writing output to {}', self._filename)

    def _sched_gzip(self):
        def _on_done(fut):
            filename, proc_time = fut.result()
            log.info('gzipped file {} took {:0.2f}s', filename, proc_time)

        coro = self._loop.run_in_executor(None,
                                          Recorder._gzip_file,
                                          self._filename)
        coro.add_done_callback(_on_done)
        coro = asyncio.shield(coro, loop=self._loop)
        asyncio.ensure_future(coro, loop=self._loop)

    @staticmethod
    def _gzip_file(filename):
        """Compress file with gzip.

        Return (filename, processing time)
        """
        t0 = time.process_time()
        with open(filename, 'rb') as f_in:
            with gzip.open(filename + '.gz', 'wb', compresslevel=9) as f_out:
                shutil.copyfileobj(f_in, f_out)
        t1 = time.process_time()
        return filename + '.gz', (t1 - t0)


def main(args):
    log.info('Starting Market Data Recorder for {}', args['<instrument>'])

    loop = asyncio.get_event_loop()

    instrument = instruments_lookup[args['<instrument>']]

    recorder = Recorder(instrument,
                        depth=int(args['--depth']),
                        interval=float(args['--interval']),
                        fmt=args['--format'],
                        output_dir=args['--output'],
                        maxfilesize=dehumanize_bytes(args['--maxsize']),
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
    with logbook.FileHandler(
            'logs/recorder_{:%Y%m%d_%H:%M:%S}.log'.format(dt.datetime.today()),
            level=logbook.INFO).applicationbound():
        args = docopt.docopt(__doc__)
        main(args)
