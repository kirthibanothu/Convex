from decimal import Decimal

from convex.common import Side, make_price, make_qty
from convex.strategy_utils.utils import PostOnlyException
from convex.strategy_utils.logger import log


'''
    Jarvis automatically updates orders in the market
        Ex:
            If we have an order that we'd like pegged to the top level
            Jarvis will update the order to keep it inline
            depending on how aggressively we want to update
'''


class Jarvis:
    def __init__(self, trader):
        self._trader = trader
        self._num_updates = 0

        self._peg_speed = Decimal(0.0)

    def update_peg(self, speed=0.02):
        self._peg_speed = Decimal(speed)

    def handle_order(self):
        pass

    async def persistent_submit(self, side, price, qty, ioc, quote):
        tries = 0
        unsuccessful_submit = True

        p = price
        q = qty

        while(tries < 5 and unsuccessful_submit):
            try:
                await self._trader.submit_order(
                        side=side, price=p, qty=q, ioc=ioc, quote=quote)
                unsuccessful_submit = False
            except PostOnlyException:
                previous_price = p
                previous_qty = q

                if side == Side.BID:
                    p = previous_price - make_price(0.01)
                    q = make_qty(
                            Decimal(round((previous_qty*previous_price)/p, 8)))
                else:
                    p = previous_price + make_price(0.01)
                    q = make_qty(
                            Decimal(round((previous_qty*previous_price)/p, 8)))
                tries += 1

        if unsuccessful_submit:
            log.warning('Tried to place order 5x. Giving up...')

    async def on_market_data(self, update):
        if self._peg_speed == Decimal(0.0):
            return

        self._num_updates += 1
        if self._num_updates > 30:
            self._num_updates = 0
            open_orders = self._trader.open_orders
            for o in open_orders:
                book = update.book
                if o.side == Side.BID:
                    if abs(book.best_bid.price - o.price) > self._peg_speed:
                        price = book.best_bid.price
                        qty = (o.remaining_qty*o.price)/price
                        await self._trader.cancel_order(o)
                        await self.persistent_submit(
                                o.side, price, qty, False, True)
                        print("Revising bid order")
                else:
                    if abs(book.best_ask.price - o.price) > self._peg_speed:
                        price = book.best_ask.price
                        qty = (o.remaining_qty*o.price)/price
                        await self._trader.cancel_order(o)
                        await self.persistent_submit(
                                o.side, price, qty, False, True)
                        print("Revising ask order")
