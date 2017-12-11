from convex.order_entry.order import Order
from convex.common import make_price, make_qty, Side
from decimal import Decimal, ROUND_DOWN

from convex.strategy_utils.logger import log


class BacktestLevelSide():
    def __init__(self, level_side):
        self._price = make_price(level_side['price'])
        self._qty = make_qty(level_side['qty'])

    @property
    def price(self):
        return self._price

    @property
    def qty(self):
        return self._qty


class BacktestBook():
    def __init__(self, book):
        self._best_bid = BacktestLevelSide(book['bids'][0])
        self._best_ask = BacktestLevelSide(book['asks'][0])

        self._book = book

    @property
    def best_bid(self):
        return self._best_bid

    @property
    def best_ask(self):
        return self._best_ask


class RestingOrdersSim():
    def __init__(self, on_trade_cb, on_cancel_cb):
        self._bids = []
        self._asks = []

        self._on_trade_cb = on_trade_cb
        self._on_cancel_cb = on_cancel_cb

    def clear(self):
        for bid in self._bids:
            self._on_cancel_cb(bid[0], bid[1], Side.BID)
        for ask in self._asks:
            self._on_cancel_cb(ask[0], ask[1], Side.ASK)

        self._bids = []
        self._asks = []

    def get_resting_value(self):
        value = Decimal(0.0)
        for bid in self._bids:
            value += bid[0]*bid[1]
        for ask in self._asks:
            value += ask[0]*ask[1]

        return value

    def add_resting(self, price, qty, side):
        # log.info("adding resting: {}, {}, {}".format(price, qty, side))
        self.clear()
        if side == Side.ASK:
            self._asks.append((price, qty))
        else:
            self._bids.append((price, qty))

    def on_market_data(self, update):
        # Get all trades and see if we get crossed against
        # If so, remove order and call on_trade_cb

        # clear any resting that would be crossing
        best_bid_price = Decimal(update['book']['bids'][0]['price'])
        best_ask_price = Decimal(update['book']['asks'][0]['price'])

        for bid in list(self._bids):
            if bid[0] >= best_ask_price:
                self._bids.remove(bid)
                self._on_cancel_cb(bid[0], bid[1], Side.BID)
                # log.info("market moved (bid)")
        for ask in list(self._asks):
            if ask[0] <= best_bid_price:
                self._asks.remove(ask)
                self._on_cancel_cb(ask[0], ask[1], Side.ASK)
                # log.info("market moved (asks)")

        trades = update['trades']
        if len(trades) == 0:
            return

        for trade in trades:
            price = Decimal(trade['price'])
            qty = Decimal(trade['qty'])
            side = trade['aggressor']
            if side == "Side.BID":
                # Take from asks side
                for i, ask in enumerate(self._asks):
                    if ask[0] < price:
                        original_ask = ask
                        # log.info(
                        #     "ASK we were traded against - mkt qty: {}".format(
                        #         qty))
                        sim_qty = Decimal(min(qty, ask[1]))

                        # update resting qty
                        # cancelled_qty = a[1] - sim_qty
                        # self._on_cancel_cb(price, cancelled_qty, Side.ASK)

                        self._on_trade_cb(price, sim_qty, Side.ASK)
                        if ask[1] == Decimal(0.0):
                            self._asks.remove(original_ask)
                        else:
                            self._asks[i] = (ask[0], ask[1]-sim_qty)
                        break
            else:
                # Take from bids side
                for i, bid in enumerate(self._bids):
                    if bid[0] < price:
                        original_bid = bid
                        # log.info(
                        #     "BID we were traded against - mkt qty: {}".format(
                        #         qty))
                        # log.info("element: {}".format(bid))
                        sim_qty = Decimal(min(qty, bid[1]))

                        # cancelled_qty = b[1] - sim_qty
                        # self._on_cancel_cb(price, cancelled_qty, Side.BID)

                        self._on_trade_cb(price, sim_qty, Side.BID)
                        if bid[1] == Decimal(0.0):
                            self._bids.remove(original_bid)
                        else:
                            self._bids[i] = (bid[0], bid[1]-sim_qty)
                        break


class BacktestTrader():
    def __init__(self):
        self._handler = None
        self._last_book = None
        self._at_min_spread = 0

        self._resting_order_sim = RestingOrdersSim(
            self.on_resting_trade, self.on_cancel)

    async def cancel_all(self):
        self._resting_order_sim.clear()

    def on_cancel(self, price, qty, side):
        # log.info("cancelling: {} {} {}".format(price, qty, side))
        if side is Side.BID:
            self._handler.update_reserves(price*qty, 0)
        else:
            self._handler.update_reserves(0, qty)

    def on_resting_trade(self, price, qty, side):
        # log.info("resting trade: {} {} {}".format(price, qty, side))
        order = Order(
            None, None, side, make_price(price),
            qty, 0, qty)

        # pretend it is like an on cancel
        if side is Side.BID:
            self._handler.update_reserves(price*qty, 0)
        else:
            self._handler.update_reserves(0, qty)

        if self._handler is not None:
            self._handler.on_fill(order, qty)

    @property
    def last_book(self):
        return self._last_book

    def on_market_data(self, update):
        self._last_book = BacktestBook(update['book'])
        self._last_ts = update['timestamp']

        self._resting_order_sim.on_market_data(update)

    def add_event_handler(self, handler):
        self._handler = handler
        handler.on_strategy_started()

    async def submit_order(self, side, price, qty, ioc=False, quote=False):
        # log.info(
        #     'Submit order | Side:{} | Price:{} | Qty:{} |'.format(
        #         side, price, qty))
        remaining_qty = qty
        depth = 0

        while (remaining_qty > 0 and depth < 1):
            '''
            available_qty = 0
            trade_price = 0
            if side == Side.BUY:
                available_qty = Decimal(
                        self._last_book._book['asks'][depth]['qty'])
                trade_price = Decimal(
                        self._last_book._book['asks'][depth]['price'])
            else:
                available_qty = Decimal(
                        self._last_book._book['bids'][depth]['qty'])
                trade_price = Decimal(
                        self._last_book._book['bids'][depth]['price'])

            filled_qty = min(available_qty, qty)
            '''
            spread = round(
                Decimal(self._last_book._book['asks'][depth]['price']) -
                Decimal(self._last_book._book['bids'][depth]['price']), 2)

            at_min_spread = spread == Decimal((0, (0, 0, 1), -2))

            depth += 1

            if not at_min_spread:
                # log.info("Spread: {}".format(spread))
                # Add resting order at best price (for market) price possible
                if side == Side.ASK:
                    if self._handler is not None:
                        bid_price = self._last_book._book['asks'][1]['price']
                        p = round(
                            Decimal(bid_price)+Decimal((0, (0, 0, 1), -2)), 2)
                        scaled_qty = Decimal(
                            (qty*price)/p).quantize(Decimal('0.01'), rounding=ROUND_DOWN)
                        self._handler.update_reserves(
                            0, Decimal('-1')*scaled_qty)
                        self._resting_order_sim.add_resting(
                            p, scaled_qty, Side.ASK)
                else:
                    if self._handler is not None:
                        ask_price = self._last_book._book['bids'][1]['price']
                        p = round(
                            Decimal(ask_price)-Decimal((0, (0, 0, 1), -2)), 2)
                        scaled_qty = Decimal(
                            (qty*price)/p).quantize(Decimal('0.01'), rounding=ROUND_DOWN)

                        self._handler.update_reserves(
                            Decimal('-1')*scaled_qty*p, 0)
                        self._resting_order_sim.add_resting(
                            p, scaled_qty, Side.BID)
                # log.info("Resting Value: {}. ".format(
                #     self._resting_order_sim.get_resting_value()))
                return

            '''
            remaining_qty -= filled_qty

            order = Order(
                None, None, side, make_price(trade_price),
                filled_qty, 0, filled_qty)

            if self._handler is not None:
                if at_min_spread:
                    self._at_min_spread += 1
                self._handler.on_fill(order, filled_qty)

                fee = filled_qty*trade_price*Decimal((0.25/100))
                self._handler.apply_fees(side, trade_price, fee)

                # log.info("Strategy Value: {}".format(
                #     self._handler.get_strategy_value(self._last_book)))
            '''
        # if remaining_qty > 0:
        #     log.info("Qty: {}, Remaining: {}, Unfilled: {}",
        #              qty, remaining_qty, qty - remaining_qty)

    def get_strategy_value(self):
        return self._handler.get_strategy_value(self._last_book)

    async def submit_ioc(self, **kwards):
        pass

    async def cancel_order(self, order):
        pass

    async def cancel_session(self):
        pass
