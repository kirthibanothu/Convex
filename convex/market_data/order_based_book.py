from collections import OrderedDict
import operator

from sortedcontainers import SortedDict

from convex.common.side import Side

from .book import Book, Level


class OrderBasedLevel(Level):
    __slots__ = '_price', '_orders'

    def __init__(self, price):
        self._price = price
        # OrderID -> quantity
        self._orders = OrderedDict()

    @property
    def price(self):
        return self._price

    @property
    def qty(self):
        return sum(self._orders.values())

    @property
    def empty(self):
        return self.orders == 0

    @property
    def orders(self):
        return len(self._orders)

    def orders_view(self):
        """Return list of orders in insertion order."""
        return self._orders

    def add_order(self, order_id, qty):
        """Add order to level."""
        self._orders[order_id] = qty

    def match_order(self, order_id, trade_qty):
        """Match resting order.

        Remove ``trade_qty`` from resting order
        """
        self._orders[order_id] -= trade_qty
        resting_qty = self._orders[order_id]
        if resting_qty <= 0:
            del self._orders[order_id]
        assert(resting_qty >= 0)

    def change_order(self, order_id, new_qty):
        """Reduce order quantity.

        Return True if order was in level, false otherwise.
        """
        if order_id in self._orders:
            self._orders[order_id] = new_qty
            return True
        return False

    def remove_order(self, order_id):
        """Remove order.

        Return True if order was in level, false otherwise.
        """
        return self._orders.pop(order_id, None) is not None


class OrderBasedBook:
    def __init__(self):
        self._bids = SortedDict(operator.neg)
        self._asks = SortedDict()

    def add_order(self, side, order_id, price, qty):
        lvl = self._fetch_level(side, price)
        lvl.add_order(order_id, qty)

    def change_order(self, side, order_id, price, new_qty):
        """Change quantity for order.

        Returns True if order exists in book, false otherwise.
        """
        lvl = self._fetch_level(side, price)
        return lvl.change_order(order_id, new_qty)

    def match_order(self, side, order_id, price, trade_qty):
        lvl = self._fetch_level(side, price)
        lvl.match_order(order_id, trade_qty)
        if lvl.empty:
            self._remove_level(side, price)

    def remove_order(self, side, order_id, price):
        lvl = self._fetch_level(side, price)
        removed = lvl.remove_order(order_id)
        if lvl.empty:
            self._remove_level(side, price)
        return removed

    def clear(self):
        self._bids.clear()
        self._asks.clear()

    def make_book(self, sequence):
        """Return ``market_data.Book`` for OrderBasedBook."""
        return Book(
                sequence=sequence,
                bids=list(self._bids.values()),
                asks=list(self._asks.values()))

    def _fetch_level(self, side, price):
        levels = self._choose_side(side)
        return OrderBasedBook._get_level(price, levels)

    def _remove_level(self, side, price):
        levels = self._choose_side(side)
        levels.pop(price, None)

    def _choose_side(self, side):
        return self._bids if side == Side.BID else self._asks

    @staticmethod
    def _get_level(price, levels):
        if price not in levels:
            levels[price] = OrderBasedLevel(price=price)
        return levels[price]
