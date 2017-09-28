import asyncio
from decimal import Decimal
from logger import log
from collections import namedtuple

from convex.common import Side, make_price, make_qty

from basic_order_manager import BasicOrderManager
from basic_pnl_manager import BasicPnLManager


PendingOrder = namedtuple("PendingOrder", ["price", "qty", "side"])


class Strategy():
    def __init__(self, trader, broadcast_cb, params={}):
        self._trader = trader
        self._order_manager = BasicOrderManager(trader._session)
        self._pnl_manager = BasicPnLManager(
                               get_balance_cb=self._trader.get_balance,
                               broadcast_cb=broadcast_cb,
                               crypto_coins=2,
                               cash_value=100)

        self._trader._session.add_event_handler(self._pnl_manager)

        self._params = params
        self._prev_book = None

        self._enabled = False
        self._pnl_manager.on_strategy_paused()

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

    # Private Utilities
    def _slacked_price(self, price):
        return round(make_price(price), 2)

    def _slacked_qty(self, qty):
        return round(make_qty(qty), min(self._params['slack'], 8))

    def _get_target_position(self, price):
        low = self._params['low']
        high = self._params['high']

        width = high - low
        return 1 - ((price - low) / width)

    def _compute_orders(self, book, targets):
        # TODO: Need to test and refactor!

        # Targets [[price, target crypto], []]
        # Need to compute order qty

        # Cannot send more orders than this value
        # TODO: This should be crypto coins, not value
        # TODO: When we place and order, make sure that the we
        # check to see that we have enough coin
        # to do so.
        crypto_val = self._pnl_manager.get_crypto_value(book)
        cash_val = self._pnl_manager.get_cash_value()

        mkt_price = self._pnl_manager.get_mkt_price(book)
        strat_value = self._pnl_manager.get_strategy_value(book)

        crypto_at_mkt_price = crypto_val / strat_value

        bids = []
        asks = []
        # handle bids
        previous_percentage = crypto_at_mkt_price
        # log.info("previous percentage: {}".format(previous_percentage))
        show = self._params['show']
        for t in reversed(targets):
            if t[0] < mkt_price:
                if show > 0:
                    price = t[0]
                    target_percentage = t[1]

                    # Buy more as we go below our mid point price,
                    # so target should be bigger
                    if previous_percentage > target_percentage:
                        # Need to send out 2 orders
                        # One at mid point and one at price t[0]

                        mkt_target = self._get_target_position(mkt_price)

                        mkt_diff = previous_percentage - mkt_target
                        if mkt_diff > 0:
                            ask_price = book.best_ask.price
                            qty = (mkt_diff*strat_value)/ask_price
                            if (round(make_qty(qty), 2) > 0.0):
                                asks.append(
                                    PendingOrder(
                                        self._slacked_price(ask_price),
                                        self._slacked_qty(qty),
                                        Side.ASK))

                                crypto_val -= ask_price*qty

                        # Own too much-send out an ask order at best bid price
                        diff = target_percentage - mkt_target
                        qty = (diff*strat_value)/price
                        if (round(make_qty(qty), 2) > 0.0):
                            bids.append(
                                PendingOrder(self._slacked_price(price),
                                             self._slacked_qty(qty),
                                             Side.BID))

                            cash_val -= price*qty
                    else:
                        diff = target_percentage - previous_percentage

                        qty = (diff*strat_value)/price
                        if (round(make_qty(qty), 2) > 0.0):
                            bids.append(
                                PendingOrder(
                                    self._slacked_price(price),
                                    self._slacked_qty(qty),
                                    Side.BID))

                            cash_val -= price*qty

                    previous_percentage = target_percentage
                show -= 1

        # handle asks
        previous_percentage = crypto_at_mkt_price
        show = self._params['show']
        for t in targets:
            if t[0] > mkt_price:
                if show > 0:
                    price = t[0]
                    target_percentage = Decimal(t[1])

                    # Sell more as we go above our mid point price,
                    # so target should be smaller
                    # Handle Best Ask Order Seperately
                    if previous_percentage < target_percentage:
                        # Need to send out 2 orders
                        # one at mid point and one at price t[0]

                        mkt_target = self._get_target_position(mkt_price)

                        mkt_diff = mkt_target - previous_percentage
                        if mkt_diff > 0:
                            bid_price = book.best_bid.price
                            qty = (mkt_diff*strat_value)/bid_price
                            if (round(make_qty(qty), 2) > 0.0):
                                bids.append(
                                    PendingOrder(
                                        self._slacked_price(bid_price),
                                        self._slacked_qty(qty),
                                        Side.BID))

                                cash_val -= bid_price*qty

                        # Own too little-send out a bid order at best bid price
                        diff = mkt_target - target_percentage
                        qty = (diff*strat_value)/price
                        if (round(make_qty(qty), 2) > 0.0):
                            asks.append(
                                PendingOrder(
                                    self._slacked_price(price),
                                    self._slacked_qty(qty),
                                    Side.ASK))

                            crypto_val -= price*qty
                    else:
                        diff = previous_percentage - target_percentage
                        qty = (diff*strat_value)/price
                        if (round(make_qty(qty), 2) > 0.0):
                            asks.append(
                                PendingOrder(
                                    self._slacked_price(price),
                                    self._slacked_qty(qty),
                                    Side.ASK))

                            crypto_val -= price*qty

                    previous_percentage = target_percentage
                show -= 1

        # log.info("Asks: {}".format(asks))
        # log.info("Bids: {}".format(bids))

        return [bids, asks]

    def _generate_targets(self, width, num_orders, low, book):
        targets = []

        increment = width / num_orders
        price = low + (increment/2)
        target = self._get_target_position(price)
        targets.append([Decimal(round(price, 2)), Decimal(round(target, 2))])

        for x in range(1, num_orders):
            price = price + increment
            target = self._get_target_position(price)
            targets.append(
                    [Decimal(round(price, 2)), Decimal(round(target, 2))])

        return targets

    async def _do_strategy(self, update):
        if not self._enabled:
            return

        num_orders = self._params['orders']

        low = self._params['low']
        high = self._params['high']

        width = high - low

        targets = self._generate_targets(width, num_orders, low, update.book)
        orders = self._compute_orders(update.book, targets)

        open_orders = self._trader._session.open_orders

        open_orders_map = {}
        open_orders_set = set()
        for o in open_orders:
            open_orders_set.add(
                PendingOrder(
                    round(o.price, 2),
                    round(o.remaining_qty, 2), o.side))

            open_orders_map[round(o.price, 2)] = o

        pending_orders_set = set(orders[0] + orders[1])

        orders_to_add = pending_orders_set - \
            pending_orders_set.intersection(open_orders_set)
        orders_to_cancel = open_orders_set - \
            pending_orders_set.intersection(open_orders_set)

        await self._dispatch_order_actions(orders_to_cancel,
                                           orders_to_add,
                                           open_orders_map)

    async def _dispatch_cancel_actions(self, to_cancel, open_orders_map):
        cancel_tasks = []
        canceling_orders = ""
        for o in to_cancel:
            open_order = open_orders_map[round(o.price, 2)]
            if open_order.is_open:
                canceling_orders += " "+str(o.price)+", "+str(o.qty)+"|"

                task = asyncio.ensure_future(
                        self._trader.cancel_order(open_order))
                cancel_tasks.append(task)

        await asyncio.gather(*cancel_tasks)

        if to_cancel:
            log.info('Cancelled Orders: {}', canceling_orders)

    async def _dispatch_submit_actions(self, to_add, open_orders_map):
        submit_tasks = []
        adding_orders = ""
        for o in to_add:
            adding_orders += " " + str(round(o.price, 2)) + \
                             ", " + str(round(o.qty, 2)) + "|"

            task = asyncio.ensure_future(
                    self._trader.submit_order(
                        side=o.side,
                        price=round(o.price, 2),
                        qty=round(o.qty, 2),
                        ioc=False,
                        quote=True))
            submit_tasks.append(task)

        await asyncio.gather(*submit_tasks)

        if to_add:
            log.info('Added Orders: {}', adding_orders)

    async def _dispatch_order_actions(self,
                                      to_cancel,
                                      to_add,
                                      open_orders_map):
        await self._dispatch_cancel_actions(to_cancel, open_orders_map)
        await self._dispatch_submit_actions(to_add, open_orders_map)

    async def on_market_data(self, update):
        await self._pnl_manager.on_market_data(update)
        await self._order_manager.on_market_data(update)

        await self._do_strategy(update)

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

        if (self._prev_book is not None) and self._trader._session.open_orders:
            # We have orders in the market, and parameters were changed by
            # the user. Recompute and update orders
            if old_params['orders'] != self._params['orders']:
                # Cancel all existing orders and recreate the orders
                # TODO: come up with a better way that doesn't require
                #       cancelling all orders.
                #       Perhaps implement revises
                await self._trader.cancel_session()
                await self.create_orders(self._prev_book)
            else:
                await self.update_orders(self._prev_book)
