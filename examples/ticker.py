#!/usr/bin/env python3

import asyncio
import json
import logging
import os

import aiohttp
from aiohttp import web

from convex.common.instrument import make_btc_usd
from convex.exchanges import ExchangeID
from convex.market_data import Subscriber as MDSubscriber
from convex.exchanges import gdax

LOG_FORMAT = '%(asctime)s.%(msecs)03d: %(levelname)s | %(message)s | [%(module)s] [%(funcName)s]'
logging.basicConfig(format= LOG_FORMAT, datefmt='%Y-%m-%d %H:%M:%S', level=logging.INFO)

WS_FILE = os.path.join(os.path.dirname(__file__), '../web/templates/ticker.html')

class WebServer:
    def __init__(self):
        pass

    async def init(self, loop, ip, port):
        self.app = web.Application(loop=loop)

        # Static routes
        self.app.router.add_static(prefix='/static/', path='web/static/', name='static', show_index=True)

        self.app['sockets'] = []
        self.app.router.add_get('/ws', self.socket_handler)
        handler = self.app.make_handler()
        await loop.create_server(handler, ip, port)

        self.session = aiohttp.ClientSession()
        self.ws = await self.session.ws_connect('ws://{}:{}/ws'.format(ip, port))
        logging.info('Running web server at {}:{}'.format(ip, port))

    def send_str(self, data):
        self.ws.send_str(data)

    async def root_handler(self, request):
        with open(WS_FILE, 'rb') as fp:
            return web.Response(body=fp.read(), content_type='text/html')

    async def socket_handler(self, request):
        resp = web.WebSocketResponse()
        ok, protocol = resp.can_prepare(request)
        if not ok:
            return web.Response(text='Somthing went wrong')

        await resp.prepare(request)

        try:
            for ws in request.app['sockets']:
                ws.send_str('someone joined')
            request.app['sockets'].append(resp)
            async for msg in resp:
                if msg.type == web.WSMsgType.TEXT:
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
                ws.send_str('Someone disconnected')
                return resp

async def poll_subscriber(sub, web_server):
    await asyncio.sleep(2)
    while True:
        update = await sub.fetch()
        web_server.send_str(json.dumps(update.top_level_json()))
        await asyncio.sleep(1)

class Ticker:
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

    async def run(self, web_params):
        await self.start_web_server()

        gw = gdax.MDGateway(loop = self.loop)
        sub = MDSubscriber(make_btc_usd(ExchangeID.GDAX), gateway=gw)

        tasks = [
                    asyncio.ensure_future(
                        self.launch_gw(gw)
                    ),
                    asyncio.ensure_future(
                        poll_subscriber(sub, self.web_server)
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

def main():
    # Rapid Development Tip:
    #   Use Browser-Sync as follows for GUI devel: (will auto refresh browser on file change)
    #       $browser-sync start --proxy http://localhost:5001/ --files="templates/**" --port=5002

    # TODO: Parameterize the following:
    web_params = {'ip': '0.0.0.0', 'port': 5001}

    loop = asyncio.get_event_loop()

    ticker = Ticker(loop)
    loop.run_until_complete(ticker.run(web_params))

if __name__ == '__main__':
    main()
