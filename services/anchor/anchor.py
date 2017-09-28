#!/usr/bin/env python3
"""Anchor Trading Strategy

Usage:
    ./dumbo.py <API_KEY> <API_SECRET> <PASSPHRASE>
               <IP> <PORT> <SANDBOX> <INSTRUMENT>
"""

import docopt
import asyncio

# For StrategyParams
from datetime import datetime

from logger import log

from trader import Trader
from web_server import WebServer
from strategy import Strategy
from utils import to_json

from convex.common.instrument import instruments_lookup
from convex.common import make_price, make_qty

from convex.market_data import Subscriber as MDSubscriber
from convex.exchanges import gdax


StrategyConfig = {}


class Anchor:
    def __init__(self, loop=None):
        if loop:
            self.loop = loop
        else:
            self.loop = asyncio.get_event_loop()

        StrategyConfig['parameters'] = {
                "last_update": str(datetime.now()),
                "high": 90,
                "low": 10,
                "orders": 2,
                "show": 1,
                "slack": 2,
                "md_refresh": 2,
                "state_refresh": 3,
                "change_crypto": 0,
                "change_cash": 0
            }

    async def launch_market_data(self):
        await self.marketDataGw.launch()

        await self.marketDataGw.request_shutdown()

    async def launch_order_adapter(self):
        await self.orderEntryGw.launch()

    async def start_web_server(self):
        self.web_server = WebServer(self.on_web_msg)

    async def run(self, params):
        await self.start_web_server()

        StrategyConfig["instrument"] = instruments_lookup[params['instrument']]

        # Start up the Market Data
        self.marketDataGw = gdax.MDGateway(loop=self.loop)
        sub = MDSubscriber(StrategyConfig["instrument"],
                           gateway=self.marketDataGw)

        # Start up the Order Adapter
        if params['sandbox']:
            api_url = gdax.OrderEntryGateway.SANDBOX_URL
        else:
            api_url = gdax.OrderEntryGateway.API_URL

        self.orderEntryGw = gdax.OrderEntryGateway(
                                api_url=api_url,
                                api_key=params['api_key'],
                                secret_key=params['api_secret'],
                                passphrase=params['passphrase'],
                                loop=self.loop
                            )

        # Start up the trader
        self.trader = Trader(
                          gateway=self.orderEntryGw,
                          instrument=StrategyConfig["instrument"],
                          limits=StrategyConfig['limits']
                      )

        self.strategy = Strategy(self.trader, self.web_server.broadcast_msg)

        await self.web_server.init(
            self.loop,
            params['ip'],
            params['port'],
            StrategyConfig["instrument"]
        )

        tasks = [
                    asyncio.ensure_future(self.launch_market_data()),
                    asyncio.ensure_future(self.launch_order_adapter()),
                    asyncio.ensure_future(self.poll_sub(sub, self.web_server))
                ]
        self._future_tasks = asyncio.ensure_future(
                                 asyncio.gather(*tasks, loop=self.loop))

        try:
            await self._future_tasks
        except asyncio.CancelledError:
            self.orderEntryGw.shutdown()

    async def poll_sub(self, sub, web_server):
        log.info('Starting Anchor Strategy')
        await asyncio.sleep(3)

        is_valid_book = False
        while not is_valid_book:
            update = await sub.fetch()
            if len(update.book.bids) > 0 and len(update.book.asks) > 0:
                await self.initialize_state(update)
                await self.strategy.on_parameters(StrategyConfig['parameters'])
                await self.strategy.on_market_data(update)
                is_valid_book = True
            else:
                await asyncio.sleep(1)

        while True:
            update = await sub.fetch()
            await self.strategy.on_market_data(update)

            # TODO: if we get traded against, we would want to
            # let the startegy take an action - poll at a faster rate
            # and check to see if anything happened, otherwise, yield control
            # at the configured interval
            await asyncio.sleep(StrategyConfig['parameters']['md_refresh'])

    async def broadcast_config(self):
        await self.web_server.broadcast_msg(
            'update',
            'Parameters',
            to_json(StrategyConfig['parameters'])
        )

    async def on_web_msg(self, msg):
        if 'admin' in msg:
            if msg['admin'] == 'GetConfig':
                await self.broadcast_config()
            elif msg['admin'] == 'StartStrategy':
                await self.strategy.start()
            elif msg['admin'] == 'StopStrategy':
                await self.strategy.pause()
            elif msg['admin'] == 'ResetPnLReference':
                self.strategy.reset_pnl_reference()

        elif 'config' in msg:
            # Validate params
            low = msg['config']['low']
            high = msg['config']['high']
            if (low >= high):
                return
            if (msg['config']['orders'] <= 0):
                return

            StrategyConfig['parameters'] = msg['config']
            StrategyConfig['parameters']['last_update'] = datetime.now()

            await self.strategy.on_parameters(StrategyConfig['parameters'])
            await self.broadcast_config()

        await self.strategy.broadcast_pnl()

    # ----------------------------------------------------------------------------------------
    # State Management Logic

    async def init_balances(self):
        # Get balances
        balance = await self.trader.get_balance()
        log.info('Initial Balance: {}', balance)

        StrategyConfig["last_update_time"] = datetime.now()
        StrategyConfig["initial_state"] = {"start_time": datetime.now(),
                                           "balances": balance}

    async def init_pnl(self, update):
        price = (update.book.best_bid.price + update.book.best_ask.price) / 2

        base = StrategyConfig["initial_state"]["balances"]["base"]
        base_value = base["available"] + base["hold"]

        quote = StrategyConfig["initial_state"]["balances"]["quote"]
        quote_value = quote["available"] + quote["hold"]

        starting_pnl = base_value*price + quote_value
        StrategyConfig["initial_state"]["starting_pnl"] = starting_pnl

    async def initialize_state(self, update):
        log.info("Initializing state: Cancelling outstanding orders...")

        # Cancel all outstanding ordes
        await self.trader.cancel_all()
        await self.init_balances()
        await self.init_pnl(update)
        await self.broadcast_config()

        log.info('Strategy Params: {}', to_json(StrategyConfig))


def main(args):
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

    log.info(
        'Starting Anchor Strategy for {} in {} mode',
        params['instrument'],
        'SANDBOX' if params['sandbox'] else 'PRODUCTION')

    # TODO: Set up limits through configuration
    StrategyConfig['limits'] = {}
    StrategyConfig['limits']['max_order_qty'] = make_qty('2')
    StrategyConfig['limits']['max_order_value'] = make_price('1000')
    StrategyConfig['limits']['max_open_value'] = 1000

    loop = asyncio.get_event_loop()
    anchor_strategy = Anchor(loop)
    loop.run_until_complete(anchor_strategy.run(params))


if __name__ == '__main__':
    args = docopt.docopt(__doc__)
    main(args)
