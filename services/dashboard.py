#!/usr/bin/env python3
"""Dashboard

Usage:
    ./dashboard.py <IP>
"""

import asyncio
import docopt
import json
import logging
import os

import aiohttp
import aiohttp.web

from convex.market_data import Subscriber as MDSubscriber

LOG_FORMAT = '%(asctime)s.%(msecs)03d: %(levelname)s | %(message)s | [%(module)s] [%(funcName)s]'
logging.basicConfig(format= LOG_FORMAT, datefmt='%Y-%m-%d %H:%M:%S', level=logging.INFO)

WS_FILE = os.path.join(os.path.dirname(__file__), '../web/templates/dashboard.html')

class WebServer:
    def __init__(self):
        pass

    async def init(self, loop, ip, port):
        self.app = aiohttp.web.Application(loop=loop)
        self.app.router.add_static(prefix='/static/', path='web/static/', name='static', show_index=True)
        self.app['sockets'] = []
        self.app.router.add_get('/', self.root_handler)
        handler = self.app.make_handler()
        await loop.create_server(handler, ip, port)

        logging.info('Running web server at {}:{}'.format(ip, port))

    async def root_handler(self, request):
        with open(WS_FILE, 'rb') as fp:
            return aiohttp.web.Response(body=fp.read(), content_type='text/html')

# ToDo: Look into how to keep the web server alive without this
async def keep_alive():
    while True:
        await asyncio.sleep(30)

class Dashboard:
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

        tasks = [
                    asyncio.ensure_future(
                        keep_alive()
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
    web_params = {
                    'ip': args['<IP>'],
                    'port': 8000
                 }

    loop = asyncio.get_event_loop()

    dashboard = Dashboard(loop)
    loop.run_until_complete(dashboard.run(web_params))

if __name__ == '__main__':
    args = docopt.docopt(__doc__)
    main(args)
