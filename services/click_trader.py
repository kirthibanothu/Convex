#!/usr/bin/env python3
"""GDAX Order Entry Example Script

Usage:
    ./click_trader.py <API_KEY> <API_SECRET> <PASSPHRASE> <IP> <PORT> <SANDBOX> <INSTRUMENT>
"""
import aiohttp
import aiohttp.web

import json
import docopt
import logbook
import asyncio
import logging
import numbers

from convex.common.instrument import instruments_lookup
from convex.exchanges import ExchangeID
from convex.common.app import AsyncApp
from convex.common import Instrument, Side, make_price, make_qty

from convex.order_entry.session import Session
from convex.order_entry import exceptions as oe_exceptions
from convex.order_entry.limit_checker import LimitChecker
from convex.exchanges import gdax

LOG_FORMAT = '%(asctime)s.%(msecs)03d: %(levelname)s | %(message)s | [%(module)s] [%(funcName)s]'
logging.basicConfig(format= LOG_FORMAT, datefmt='%Y-%m-%d %H:%M:%S', level=logging.INFO)

class Trader:
    def __init__(self, gateway, instrument):
        limits = LimitChecker(max_order_qty=make_qty('100'),
                              max_order_value=make_price('20000'),
                              max_open_value=20000)
        self.session = Session(gateway=gateway,
                               instrument=instrument,
                               limits=limits)
        self.session.add_event_handler(self)
        self.orders = []
        self._broadcast_cb = None

    def on_fill(self, order, filled_qty):
        logging.info('Order filled: filled_qty={}, order={}'.format(filled_qty, order))
        fill = {"filled_qty": filled_qty, "order": order.dump()}
        if (self._broadcast_cb):
            self._broadcast_cb("on_fill", fill)

    def on_complete(self, order):
        logging.info('Order completed: order={}'.format(order))
        if (self._broadcast_cb):
            self._broadcast_cb("on_complete", order.dump())

    async def get_balance(self):
        base, quote = await self.session.get_balances()
        return {
                   'base': {
                       'available': float(base['available']),
                       'hold': float(base['hold'])
                   },
                   'quote': {
                       'available': float(quote['available']),
                       'hold': float(quote['hold'])
                   }
               }

    async def get_fills(self):
        return await self.session.get_fills()

    def log_balance(self, balance):
        logging.info('Balances: base=avail:{}|hold:{}, quote=avail:{}|hold:{}'.format(
            balance['base']['available'], balance['base']['hold'],
            balance['quote']['available'], balance['quote']['hold']))

    def log_exch_orders(self, orders):
        logging.info('Open orders: {}'.format(orders))

    async def init(self, broadcast_cb):
        await self.session.wait_ready()
        self._broadcast_cb = broadcast_cb

    async def broadcast_order_ack(self, msg_type, order):
        logging.info("Submitted order for {}".format(order))
        if (self._broadcast_cb):
            self._broadcast_cb(msg_type, order)
            await self.broadcast_balance()
            await self.broadcast_orders()

    async def broadcast_orders(self):
        exch_orders = await self.session.exch_orders()
        #self.log_exch_orders(exch_orders)
        if (self._broadcast_cb):
            self._broadcast_cb("open_orders", exch_orders)

    async def broadcast_balance(self):
        balance = await self.get_balance()
        self.log_balance(balance)
        if (self._broadcast_cb):
            self._broadcast_cb("balance", balance)

    def broadcast_error(self, error_type, error, trigger):
        logging.error(error)
        msg = {'error': str(error), 'trigger': trigger}
        if (self._broadcast_cb):
            self._broadcast_cb(error_type, msg)

    async def submit_order(self, **kwargs):
        try:
            order = await self.session.submit(**kwargs)
            self.orders.append(order)

            if (order):
                await self.broadcast_order_ack("submit_ack", order.dump())
            return order
        except oe_exceptions.SubmitNack as nack:
            self.broadcast_error('submit_nack', nack, {'msg': 'submit', 'args': ''})
        except oe_exceptions.LimitError as limiterror:
            self.broadcast_error('limit_error', limiterror, {'msg': 'submit', 'args': ''})
        except oe_exceptions.InternalNack as internalnack:
            self.broadcast_error('internal_nack', internalnack, {'msg': 'submit', 'args': ''})
        except oe_exceptions.OrderError as ordererror:
            self.broadcast_error('order_error', ordererror, {'msg': 'submit', 'args': ''})
        except Exception as e:
            logging.error('Unhandled error [{}] when trying to submit order.'.format(e))

    async def submit_ioc(self, **kwargs):
        try:
            order = await self.session.submit_ioc(**kwargs)
            self.orders.append(order)

            if (order):
                await self.broadcast_order_ack("submit_ack", order.dump())

            return order
        except oe_exceptions.SubmitNack as nack:
            self.broadcast_error('submit_nack', nack, {'msg': 'submit_ioc', 'args': ''})
        except oe_exceptions.LimitError as limiterror:
            self.broadcast_error('limit_error', limiterror, {'msg': 'submit_ioc', 'args': ''})
        except oe_exceptions.InternalNack as internalnack:
            self.broadcast_error('internal_nack', internalnack, {'msg': 'submit_ioc', 'args': ''})
        except oe_exceptions.OrderError as ordererror:
            self.broadcast_error('order_error', ordererror, {'msg': 'submit_ioc', 'args': ''})
        except Exception as e:
            logging.error('Unhandled error [{}] when trying to submit order.'.format(e))

    async def cancel_session(self):
        try:
            await self.session.cancel_session()
            await self.broadcast_balance()
            await self.broadcast_orders()

        except oe_exceptions.CancelNack as nack:
            self.broadcast_error('cancel_nack', nack, {'msg': 'cancel_session', 'args': ''})
        except Exception as e:
            logging.error('Unhandled error [{}] when trying to cancel session orders.'.format(e))

    async def cancel_all(self):
        try:
            await self.session.cancel_all()
            await self.broadcast_balance()
            await self.broadcast_orders()

        except oe_exceptions.CancelNack as nack:
            self.broadcast_error('cancel_all_nack', nack, {'msg': 'cancel_all', 'args': ''})
        except Exception as e:
            logging.error('Unhandled error [{}] when trying to cancel all orders.'.format(e))

def is_valid_submit(submit):
    try:
        return all(submit[k] is not None for k in ('side', 'quote', 'qty', 'price', 'ioc', 'side'))
    except Exception as e:
        logging.exception('IsValidSubmit check failed. Msg: {}'.format(submit))
        return False

class WebServer:
    def __init__(self):
        pass

    async def init(self, loop, ip, port, trader, instrument):
        self.trader = trader
        self.instrument = instrument

        await self.trader.init(self.broadcast)

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


    def broadcast(self, msg_type, msg):
        resp = {}
        actions = {}
        actions['msg_type'] = msg_type
        actions['msg'] = msg
        resp['actions'] = actions

        msg = json.dumps(resp)
        self.send_str(msg)

    def send_str(self, data):
        for ws in self.app['sockets']:
            ws.send_str(data)

    async def get_balance_msg(self):
        balance = await self.trader.get_balance()
        response = {}

        response['balance'] = balance

        instrument = {}
        instrument['base'] = self.instrument.base
        instrument['quote'] = self.instrument.quote

        response['instrument'] = instrument
        return response

    async def get_fills_msg(self):
        fills = await self.trader.get_fills()
        resp = {}
        actions = {}
        actions['msg_type'] = 'fills'
        actions['msg'] = fills
        resp['actions'] = actions

        return resp

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
                        if is_valid_submit(req['submit']):
                            submit = req['submit']
                            side = Side.BUY if submit['side'] == 'BUY' else Side.SELL

                            submit = await self.trader.submit_order(
                                          side=side,
                                          price=make_price(submit['price']),
                                          qty=make_qty(submit['qty']),
                                          ioc=submit['ioc'],
                                          quote=submit['quote'])
                        else:
                            self.broadcast('submit_nack', {'trigger': {'msg': 'submit', 'args': req}, 'error': 'One or more fields are invalid!'})
                    elif 'cancel_session' in req:
                        await self.trader.cancel_session()
                    elif 'cancel_all' in req:
                        await self.trader.cancel_all()
                    elif 'admin' in req:
                        if req['admin'] == 'GetBalance':
                            msg = await self.get_balance_msg()
                            resp.send_str(json.dumps(msg))
                        elif req['admin'] == 'ListOrders':
                            await self.trader.broadcast_orders()
                        elif req['admin'] == 'GetFills':
                            msg = await self.get_fills_msg()
                            resp.send_str(json.dumps(msg))
                else:
                    pass
        except Exception as e:
            self.broadcast('UnexpectedError', e)
            logging.error('Unexpected Error: {}'.format(e))
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

        api_url = gdax.OrderEntryGateway.SANDBOX_URL if params['sandbox'] else gdax.OrderEntryGateway.API_URL
        self.gw = gdax.OrderEntryGateway(
                           api_url=api_url,
                           api_key=params['api_key'],
                           secret_key=params['api_secret'],
                           passphrase=params['passphrase'],
                           loop=self.loop)

        instrument = instruments_lookup[params['instrument']]

        self.trader = Trader(gateway=self.gw, instrument=instrument)

        await self.launch_gw()
        tasks = [
                    asyncio.ensure_future(
                        keep_alive()
                    ),
                    asyncio.ensure_future(
                        self.web_server.init(
                            self.loop, params['ip'], params['port'], self.trader, instrument
                        )
                    )
                ]
        self._future_tasks = asyncio.ensure_future(asyncio.gather(*tasks, loop=self.loop))

        try:
            await self._future_tasks
        except asyncio.CancelledError:
            self.gw.shutdown()


def main(args):
    app = AsyncApp(name='click_trader')

    params = {
                 'api_url': gdax.OrderEntryGateway.SANDBOX_URL,
                 'api_key': args['<API_KEY>'],
                 'api_secret': args['<API_SECRET>'],
                 'passphrase': args['<PASSPHRASE>'],
                 'ip': args['<IP>'],
                 'port': args['<PORT>'],
                 'sandbox': False if (args['<SANDBOX>'] == "False") else True,
                 'instrument': args['<INSTRUMENT>']

             }

    logging.info("Starting Click Trader for {} in {} mode".format(params['instrument'],
                                                                  "SANDBOX" if params['sandbox'] else "PRODUCTION"))

    loop = asyncio.get_event_loop()
    click_trader = ClickTrader(loop)
    loop.run_until_complete(click_trader.run(params))

if __name__ == '__main__':
    args = docopt.docopt(__doc__)
    main(args)
