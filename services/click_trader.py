#!/usr/bin/env python3
"""GDAX Order Entry Example Script

Usage:
    ./click_trader.py <API_KEY> <API_SECRET> <PASSPHRASE> <IP> <PORT>
"""
import aiohttp
import aiohttp.web

import json
import docopt
import logbook
import asyncio
import logging

from convex.common.app import AsyncApp
from convex.common import Instrument, Side, make_price, make_qty

from convex.order_entry.session import Session
from convex.order_entry import exceptions as oe_exceptions
from convex.order_entry.limit_checker import LimitChecker
from convex.exchanges import gdax

log = logbook.Logger('EXAMPLE')

LOG_FORMAT = '%(asctime)s.%(msecs)03d: %(levelname)s | %(message)s | [%(module)s] [%(funcName)s]'
logging.basicConfig(format= LOG_FORMAT, datefmt='%Y-%m-%d %H:%M:%S', level=logging.INFO)

class Trader:
    def __init__(self, gateway, instrument):
        limits = LimitChecker(max_order_qty=make_qty('0.8'),
                              max_order_value=make_price('200.50'),
                              max_open_value=200)
        self.session = Session(gateway=gateway,
                               instrument=instrument,
                               limits=limits)
        self.session.add_event_handler(self)

    def on_fill(self, order, filled_qty):
        print(order)
        print(filled_qty)
        log.info('Order filled: filled_qty={}, order={}', filled_qty, order)

    def on_complete(self, order):
        print(order)
        log.info('Order completed: order={}', order)

    async def get_balance(self):
        base, quote = await self.session.get_balances()
        return {'base': float(base), 'quote': float(quote)}

    async def check_balance(self):
        base, quote = await self.get_balance()
        log.info('Balances: base={}, quote={}', base, quote)

    async def init(self):
        await self.session.wait_ready()
        await self.check_balance()

    async def submit_order(self, **kwargs):
        try:
            order = await self.session.submit(**kwargs)
            await self.check_balance()
            return order
        except oe_exceptions.SubmitNack as nack:
            log.error(nack)

    async def submit_ioc(self, **kwargs):
        try:
            order = await self.session.submit_ioc(**kwargs)
            await self.check_balance()
            return order
        except oe_exceptions.SubmitNack as nack:
            log.error(nack)


class WebServer:
    def __init__(self):
        pass

    async def init(self, loop, ip, port, trader):
        self.trader = trader
        await self.trader.init()

        self.app = aiohttp.web.Application(loop=loop)
        self.app.router.add_static(prefix='/static/',
                                   path='web/static/',
                                   name='static',
                                   show_index=True)
        self.app['sockets'] = []
        self.app.router.add_get('/ws', self.socket_handler)
        handler = self.app.make_handler()
        await loop.create_server(handler, ip, port)

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
            request.app['sockets'].append(resp)
            async for msg in resp:
                if msg.type == aiohttp.web.WSMsgType.TEXT:
                    req = json.loads(msg.data)
                    if 'submit' in req:
                        logging.info('Recieved request: {}'.format(req))
                        submit = req['submit']
                        side = Side.BUY if submit['side'] == 'BUY' else Side.SELL

                        submit = await self.trader.submit_order(
                                  side=side,
                                  price=make_price(submit['price']),
                                  qty=make_qty(submit['qty']),
                                  ioc=submit['ioc'],
                                  quote=submit['quote'])

                    elif 'admin' in req:
                        if req['admin'] == 'GetBalance':
                            balance = await self.trader.get_balance()
                            response = {}
                            response['balance'] = balance
                            resp.send_str(json.dumps(response))
                else:
                    pass
        except Exception as e:
            logging.error('Unexcepted Error: {}'.format(e))
        finally:
            try:
                request.app['sockets'].remove(resp)
            except ValueError:
                pass

            return resp

# ToDo: Look into how to keep the web server alive without this
async def keep_alive():
    while True:
        await asyncio.sleep(30)

class ClickTrader:
    def __init__(self, loop=None):
        if loop:
            self.loop = loop
        else:
            self.loop = asyncio.get_event_loop()

    async def launch_gw(self):
        await self.gw.launch()

    async def start_web_server(self):
        self.web_server = WebServer()

    async def run(self, params):
        await self.start_web_server()

        self.gw = gdax.OrderEntryGateway(
                           api_url=gdax.OrderEntryGateway.SANDBOX_URL,
                           api_key=params['api_key'],
                           secret_key=params['api_secret'],
                           passphrase=params['passphrase'],
                           loop=self.loop)

        instrument = Instrument.from_string('BTCUSD@GDAX')

        self.trader = Trader(gateway=self.gw, instrument=instrument)

        await self.launch_gw()
        tasks = [
                    asyncio.ensure_future(
                        keep_alive()
                    ),
                    asyncio.ensure_future(
                        self.web_server.init(
                            self.loop, params['ip'], params['port'], self.trader
                        )
                    )
                ]
        self._future_tasks = asyncio.ensure_future(asyncio.gather(*tasks, loop=self.loop))

        try:
            await self._future_tasks
        except asyncio.CancelledError:
            self.gw.shutdown()


def main(args):
    app = AsyncApp(name='gdax_oe_example')


    params = {
                 'api_url': gdax.OrderEntryGateway.SANDBOX_URL,
                 'api_key': args['<API_KEY>'],
                 'api_secret': args['<API_SECRET>'],
                 'passphrase': args['<PASSPHRASE>'],
                 'ip': args['<IP>'],
                 'port': args['<PORT>']
             }

    loop = asyncio.get_event_loop()
    click_trader = ClickTrader(loop)
    loop.run_until_complete(click_trader.run(params))

if __name__ == '__main__':
    args = docopt.docopt(__doc__)
    main(args)
