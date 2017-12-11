#!/usr/bin/env python3
"""Smart MarketData

Usage:
    ./smart_md.py <IP> <PORT> <INTERVAL> <INSTRUMENTS>

"""

import asyncio
import datetime as dt
import docopt
import logbook
import time
from convex.market_data import Subscriber as MDSubscriber
from convex.common.instrument import instruments_lookup
from convex.strategy_utils.utils import weighted_midpoint

import aiohttp
import aiohttp.web
import json
from pprint import pprint

from convex.strategy_utils.utils import json_serial
from convex.exchanges import gdax


log = logbook.Logger('SmartMD')


class WebServer:
    def __init__(self, message_cb):
        self.cb = message_cb
        pass

    async def init(self, loop, ip, port):
        self._app = aiohttp.web.Application(loop=loop)
        self._app['sockets'] = set()
        self._app.router.add_get('/ws', self.socket_handler)
        self._handler = self._app.make_handler()

        self._srv = await loop.create_server(self._handler, ip, port)
        self._session = aiohttp.ClientSession()

        log.info('Running web server at {}:{}', ip, port)

    async def add_handler(self, instrument, topic):
        if instrument not in self._app:
            self._app[instrument] = {}
            if topic not in self._app[instrument]:
                self._app[instrument][topic] = set()

    async def broadcast_msg(self, name, msg_type, msg):
        resp = {name: {'type': msg_type, 'msg': msg}}
        await self.send_str(json.dumps(resp))

    async def broadcast(self, instrument, msg_type, value):
        json_msg = json.dumps(value,
                              separators=(',', ': '),
                              default=json_serial)

        for ws in self._app[instrument][msg_type]:
            await ws.send_str(json_msg)

    async def send_str(self, data):
        for ws in self._app['sockets']:
            await ws.send_str(data)

    def _on_request(self, ws, req, subscriptions):
        try:
            req_type = req['type']
            value = req['value']
            instrument = req['instrument']
            name = req['name']

            if req_type == 'subscribe':
                log.info('{} subscribing to {} for instrument {}'.format(
                    name, value, instrument))
                self._subscribe(ws, instrument, value)
                subscriptions.add((instrument, value))
            elif req_type == 'unsubscribe':
                log.info('{} unsubscribing to {} for instrument {}'.format(
                    name, value, instrument))
                self._unsubscribe(ws, instrument, value)
                subscriptions.discard((instrument, value))
            else:
                log.warning(
                    'Unhandled type: {}, val: {}, instr: {}, name: {}.'.format(
                        req_type, value, instrument, name))
        except Exception as e:
            log.exception('Msg missing required fields: {}'.format(req))

    def _subscribe(self, ws, instrument, value):
        if value == 'weighted_mid':
            try:
                self._app[instrument][value].add(ws)
                ws.send_str(json.dumps({'type': 'ack', 'value': 'succeeded'}))
            except KeyError:
                ws.send_str(
                    json.dumps({'type': 'ack', 'value': 'unsupported'}))
        else:
            ws.send_str(
                json.dumps({'type': 'ack', 'value': 'topic_not_available'}))

    def _unsubscribe(self, ws, instrument, value):
        if instrument in self._app:
            if value in self._app[instrument]:
                self._app[instrument][value].discard(ws)
                ws.send_str(json.dumps({'type': 'ack', 'value': 'succeeded'}))
                return
            ws.send_str(
                json.dumps({'type': 'ack', 'value': 'topic_not_available'}))

    async def socket_handler(self, request):
        ws = aiohttp.web.WebSocketResponse()
        ok, protocol = ws.can_prepare(request)
        if not ok:
            return aiohttp.web.Response(text='Somthing went wrong')

        await ws.prepare(request)

        request.app['sockets'].add(ws)

        subscriptions = set()
        try:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        req = json.loads(msg.data)
                        self._on_request(ws, req, subscriptions)

                    except Exception as e:
                        log.exception('Unexpected Error: {}', e)
                        await ws.close()
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    log.info('Conn closed w/ exception: {}', ws.exception())
                    await ws.close()
        finally:
            request.app['sockets'].discard(ws)
            for sub in subscriptions:
                self._app[sub[0]][sub[1]].discard(ws)

        return ws


class SmartMD:
    def __init__(self, loop=None):
        if loop:
            self._loop = loop
        else:
            self._loop = asyncio.get_event_loop()

        self._interval = 1
        self._instrument = None

    async def _launch_market_data(self, md):
        await md.launch()
        await md.request_shutdown()

    async def _start_web_server(self):
        self._web_server = WebServer(self._on_web_msg)

    async def run(self, params):
        await self._start_web_server()

        self._interval = int(params['interval'])
        self._instruments = [
            instruments_lookup[instrument]
            for instrument in params['instruments']
        ]

        self._instr_str = str(self._instrument)

        await self._web_server.init(self._loop,
                                    params['web']['ip'],
                                    params['web']['port'])

        # Start Market Data
        md_gateways = set()
        subscribers = set()
        for instrument in self._instruments:
            md_gw = gdax.MDGateway(loop=self._loop)
            md_gateways.add(md_gw)

            subscribers.add(
                MDSubscriber(instrument, gateway=md_gw))

            await self._web_server.add_handler(str(instrument), 'weighted_mid')

        tasks = []
        for md_gw in md_gateways:
            tasks.append(
                asyncio.ensure_future(self._launch_market_data(md_gw)))

        for sub in subscribers:
            tasks.append(
                asyncio.ensure_future(
                    self._poll_sub(sub, self._web_server)))

        self._future_tasks = asyncio.ensure_future(
                asyncio.gather(*tasks, loop=self._loop))

        try:
            await self._future_tasks
        except asyncio.CancelledError:
            pass

    async def _poll_sub(self, sub, web_server):
        instrument = str(sub.instrument)

        log.info('Starting polling for instrument: {}'.format(instrument))
        await asyncio.sleep(3)

        while True:
            update = await sub.fetch()
            await self._on_market_data(instrument, update)
            await asyncio.sleep(self._interval)

    async def _on_market_data(self, instrument, update):
        await self._broadcast(instrument, 'weighted_mid', {
                'ts': int(time.mktime(update.timestamp.timetuple())*1000),
                'instr': instrument,
                'price': weighted_midpoint(update.book)
            }
        )

    async def _broadcast(self, instrument, msg_type, value):
        await self._web_server.broadcast(instrument, msg_type, value)

    async def _on_web_msg(self, msg):
        pass


def main(args):
    loop = asyncio.get_event_loop()
    smart_md = SmartMD(loop)

    instruments = args['<INSTRUMENTS>'].split(',')
    params = {
                'web': {
                    'ip': args['<IP>'],
                    'port': args['<PORT>']
                },
                'instruments': instruments,
                'interval': args['<INTERVAL>']
            }

    log.info(
        'Starting Smart MarketData for {} with interval.',
        instruments, params['interval'])

    try:
        loop.run_until_complete(smart_md.run(params))
    except KeyboardInterrupt:
        log.info('Keybaord Interrupt - Shutting down Smart Market Data')

        # Cancel all running tasks
        for t in asyncio.Task.all_tasks():
            try:
                t.exception()
            except Exception:
                log.exception('Exception during shutdown: {}', t)
    finally:
        loop.close()


if __name__ == '__main__':
    with logbook.FileHandler(
            'logs/smart_md.log'.format(
                dt.datetime.today()), level=logbook.INFO).applicationbound():
        args = docopt.docopt(__doc__)
        main(args)
