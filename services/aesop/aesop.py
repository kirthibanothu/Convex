#!/usr/bin/env python3
""" Aesop Strategy
Usage:
    ./aesop.py <API_KEY> <API_SECRET> <PASSPHRASE>
               <IP> <PORT> <SANDBOX> <INSTRUMENT>

"""
import asyncio
import datetime as dt
from datetime import datetime
from decimal import Decimal
import docopt
import logbook
from web_server import WebServer
from trader import Trader

from convex.common import Side, make_price, make_qty
from convex.common.instrument import instruments_lookup

from convex.market_data import Subscriber as MDSubscriber
# Strategy Utils
from convex.strategy_utils.basic_pnl_manager import BasicPnLManager
from convex.strategy_utils.basic_order_manager import BasicOrderManager
from convex.strategy_utils.jarvis import Jarvis
from convex.strategy_utils.realized_volatility import RealizedVolatility
from convex.strategy_utils.utils import to_json

from convex.signals.ema.dual_ema import DualEMA

from convex.exchanges import gdax


log = logbook.Logger('Aesop')


StrategyConfig = {}


class Aesop:
    def __init__(self, trader, broadcast_cb):
        self._trader = trader
        self._order_manager = BasicOrderManager(trader._session)
        self._pnl_manager = BasicPnLManager(
                                get_balance_cb=self._trader.get_balance,
                                broadcast_cb=broadcast_cb,
                                crypto_coins=2,
                                cash_value=0,
                                instrument=StrategyConfig['instrument'])
        self._jarvis = Jarvis(trader)
        self._realized_volitility = RealizedVolatility()

        self._trader._session.add_event_handler(self._pnl_manager)

        self._params = StrategyConfig['parameters']

        self._prev_book = None
        self._enabled = False
        self._pnl_manager.on_strategy_paused()

        self._broadcast_cb = broadcast_cb

        self._num_updates = 0

        # Strategy Initialization
        self._dual_ema = DualEMA(
                slow=self._params['slow'],
                fast=self._params['fast'],
                on_init_cb=self.on_signal_init,
                on_signal_cb=self.on_signal)

    def _at_min_spread(self):
        spread = round(
            self._prev_book.best_ask.price -
            self._prev_book.best_bid.price, 2)

        return (spread == Decimal((0, (0, 0, 1), -2)))

    async def on_signal(self, action, update):
        if not self._enabled:
            return

        await self._trader.cancel_all()

        at_min_spread = self._at_min_spread()

        book = update['book']
        if action == 'BUY':
            if self._pnl_manager.get_cash_value() <= Decimal(1.00):
                return

            cash = Decimal(self._pnl_manager.get_cash_value())

            if at_min_spread:
                price = make_price(float(book['asks'][0]['price']))
                qty = Decimal(round(cash / price, 8))
            else:
                price = make_price(float(book['asks'][0]['price'])-0.01)
                qty = Decimal(round(cash / price, 8))

            await self._jarvis.persistent_submit(
                side=Side.BID, price=price, qty=make_qty(qty),
                ioc=False, quote=True)
        else:
            if self._pnl_manager.get_crypto_value(book) <= Decimal(0.01):
                return

            qty = Decimal(round(self._pnl_manager.crypto_coins, 8))
            if at_min_spread:
                price = make_price(float(book['bids'][0]['price']))
            else:
                price = make_price(float(book['bids'][0]['price'])+0.01)

            await self._jarvis.persistent_submit(
                side=Side.ASK, price=price, qty=make_qty(Decimal(qty)),
                ioc=False, quote=True)

        # Notify dashboard listeners
        await self._broadcast_state("Flipped Signal")

    async def _broadcast_state(self, message=''):
        strategy_state = {
                    'slow_ema': self._dual_ema.slow_value,
                    'fast_ema': self._dual_ema.fast_value,
                    'realized_volatility': self._realized_volitility.value,
                    'action': self._dual_ema.action_color,
                    'message': message
                }
        await self._broadcast_cb(
                "update", "StrategyState", to_json(strategy_state))

    async def on_signal_init(self):
        await self._broadcast_state('Strategy initialized successfully')

    # Control handlers
    async def start(self):
        log.warn('Starting strategy!')
        self._enabled = True
        self._pnl_manager.on_strategy_started()

    async def pause(self):
        log.warn('Stopping strategy!')
        self._enabled = False
        self._pnl_manager.on_strategy_paused()
        await self._trader.cancel_all()

    def reset_pnl_reference(self):
        self._pnl_manager.reset_pnl_reference()

    # Public Utilities
    async def broadcast_pnl(self):
        if self._prev_book:
            await self._pnl_manager.update(self._prev_book)
            await self._pnl_manager.broadcast()

    async def _do_strategy(self, update):
        pass

    async def on_market_data(self, update):
        update_dump = update.dump(10)

        await self._pnl_manager.on_market_data(update)
        await self._order_manager.on_market_data(update)

        # TODO: Fix this awful to dict conversion for backtesting
        if self._dual_ema.is_initialized:
            self._num_updates += 1
            await self._dual_ema.on_market_data(update_dump)
            if self._num_updates >= 15:
                self._num_updates = 0
                await self._broadcast_state()
        else:
            await self._dual_ema.initialize(update_dump)

        # await self._do_strategy(update)
        self._realized_volitility.on_market_data(update_dump)
        await self._jarvis.on_market_data(update)

        self._prev_book = update.book

    async def on_parameters(self, parameters):
        delta_crypto = parameters['change_crypto']
        delta_cash = parameters['change_cash']

        if (delta_cash != 0 or delta_crypto != 0):
            self._pnl_manager.update_reserves(delta_cash, delta_crypto)

        # Reset the change parameters
        parameters['change_crypto'] = 0
        parameters['change_cash'] = 0

        self._pnl_manager.update_refresh_interval(parameters['state_refresh'])
        # TODO: Validate parameters
        log.info(
            'Updating strategy parameters from: {} to {}',
            self._params, parameters)

        old_params = self._params
        self._params = parameters

        self._jarvis.update_peg(self._params['peg_speed'])

        if (self._params['slow'] != old_params['slow'] or
                self._params['fast'] != old_params['fast']):
            if self._trader._session.open_orders:
                await self._trader.cancel_session()

            self._dual_ema.reset(
                    slow=self._params['slow'], fast=self._params['fast'])
            await self._broadcast_state(
                    'Updating: slow {}->{}, fast {}->{}'.format(
                        old_params['slow'], self._params['slow'],
                        old_params['fast'], self._params['fast']))


class StrategyHarness:
    def __init__(self, loop=None):
        if loop:
            self.loop = loop
        else:
            self.loop = asyncio.get_event_loop()

        StrategyConfig['parameters'] = {
            "last_update": str(datetime.now()),
            "slow": 140,
            "fast": 10,
            "change_crypto": 0,
            "change_cash": 0,
            "md_refresh": 2,
            "state_refresh": 3
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

        StrategyConfig['instrument'] = instruments_lookup[params['instrument']]

        # Start up market data
        self.marketDataGw = gdax.MDGateway(loop=self.loop)
        sub = MDSubscriber(StrategyConfig['instrument'],
                           gateway=self.marketDataGw)

        # Start up the order adapter
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

        self.strategy = Aesop(self.trader, self.web_server.broadcast_msg)

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
        print(msg)
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
            slow = msg['config']['slow']
            fast = msg['config']['fast']
            if (fast >= slow):
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
    loop = asyncio.get_event_loop()
    strategy_harness = StrategyHarness(loop)

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
        'Starting Aesop Strategy for {} in {} mode',
        params['instrument'],
        'SANDBOX' if params['sandbox'] else 'PRODUCTION')

    # TODO: Set up limits through configuration
    StrategyConfig['limits'] = {}
    StrategyConfig['limits']['max_order_qty'] = make_qty('3')
    StrategyConfig['limits']['max_order_value'] = make_price('1000')
    StrategyConfig['limits']['max_open_value'] = 1000

    try:
        loop.run_until_complete(strategy_harness.run(params))
    except KeyboardInterrupt:
        log.info('Keyboard Interrupt - Shutting down Aesop Strategy')

        # Cancel all running tasks
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
            'logs/aesop_{:%Y%m%d_%H:%M:%S}.log'.format(
                dt.datetime.today()), level=logbook.INFO).applicationbound():
        args = docopt.docopt(__doc__)
        main(args)
