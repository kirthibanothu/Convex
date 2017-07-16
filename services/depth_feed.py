#!/usr/bin/env python3
"""Depth Feed

Usage:
    ./depth_feed.py <IP> <DEPTH> <SLEEP_INT> <INSTRUMENT>
"""

import asyncio
import docopt
import json
import logging
import os

import aiohttp
import aiohttp.web

from convex.common.instrument import instruments_lookup
from convex.market_data import Subscriber as MDSubscriber
from convex.exchanges import gdax

LOG_FORMAT = '%(asctime)s.%(msecs)03d: %(levelname)s | %(message)s | [%(module)s] [%(funcName)s]'
logging.basicConfig(format= LOG_FORMAT, datefmt='%Y-%m-%d %H:%M:%S', level=logging.INFO)

class WebServer:
    def __init__(self):
        pass

    async def init(self, loop, ip, port):
        self.app = aiohttp.web.Application(loop=loop)
        self.app.router.add_static(prefix='/static/',
                                   path='web/static/',
                                   name='static',
                                   show_index=True)
        self.app['sockets'] = []
        self.app.router.add_get('/ws', self.socket_handler)
        handler = self.app.make_handler()
        await loop.create_server(handler, ip, port)

        # Add app routers:

        self.session = aiohttp.ClientSession()
        self.ws = await self.session.ws_connect('ws://{}:{}/ws'.format(ip, port))
        logging.info('Running web server at {}:{}'.format(ip, port))

    def send_str(self, data):
        self.ws.send_str(data)

    async def socket_handler(self, request):
        resp = aiohttp.web.WebSocketResponse()
        ok, protocol = resp.can_prepare(request)
        if not ok:
            return aiohttp.web.Response(text='Somthing went wrong')

        await resp.prepare(request)

        try:
            for ws in request.app['sockets']:
                ws.send_str('{"ws_msg": "someone joined"}')
            request.app['sockets'].append(resp)
            async for msg in resp:
                if msg.type == aiohttp.web.WSMsgType.TEXT:
                    for ws in request.app['sockets']:
                        if ws is not resp:
                            ws.send_str(msg.data)
                else:
                    return resp
        except Exception as e:
            logging.error('Unexcepted Error: {}'.format(e))
        finally:
            try:
                request.app['sockets'].remove(resp)
            except ValueError:
                pass

            for ws in request.app['sockets']:
                ws.send_str('{"ws_msg": "Someone disconnected"}')
                return resp

async def poll_subscriber(sub, web_server, feed_params):
    await asyncio.sleep(2)
    msg = {}
    while True:
        update = await sub.fetch()
        msg['book_update'] = update.dump(feed_params['depth'])
        web_server.send_str(json.dumps(msg))
        await asyncio.sleep(feed_params['sleep_int'])

class DepthFeed:
    def __init__(self, loop=None):
        if loop:
            self.loop = loop
        else:
            self.loop = asynio.get_event_loop()

    async def launch_gw(self, gw):
        await gw.launch()
        await gw.request_shutdown()

    async def start_web_server(self):
        self.web_server = WebServer()

    async def run(self, web_params, feed_params):
        await self.start_web_server()

        instrument = instruments_lookup[feed_params['instrument']]

        gw = gdax.MDGateway(loop = self.loop)
        sub = MDSubscriber(instrument, gateway=gw)

        tasks = [
                    asyncio.ensure_future(
                        self.launch_gw(gw)
                    ),
                    asyncio.ensure_future(
                        poll_subscriber(sub, self.web_server, feed_params)
                    ),
                    asyncio.ensure_future(
                        self.web_server.init(
                            self.loop, web_params['ip'], web_params['port']
                        )
                    )
                ]
        self._future_tasks = asyncio.ensure_future(asyncio.gather(*tasks, loop=self.loop))

        try:
            await self._future_tasks
        except asyncio.CancelledError:
            pass

def main(args):
    # Rapid Development Tip:
    #   Use Browser-Sync as follows for GUI devel:
    #   (will auto refresh browser on file change)
    #       $browser-sync start --proxy http://localhost:5001/ --files="templates/**" --port=5002

    web_params = {
                    'ip': args['<IP>'],
                    'port': 8001
                 }

    feed_params = {
                    'depth': int(args['<DEPTH>']),
                    'sleep_int': float(args['<SLEEP_INT>']),
                    'instrument': args['<INSTRUMENT>']
                  }

    loop = asyncio.get_event_loop()

    depth_feed = DepthFeed(loop)
    loop.run_until_complete(depth_feed.run(web_params, feed_params))

if __name__ == '__main__':
    args = docopt.docopt(__doc__)
    main(args)
