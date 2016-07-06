from sortedcontainers import SortedDict

from common.side import Side

from .book import Book


class _OrderBasedLevel:
    __slots__ = '_price', '_orders'

    def __init__(self, price):
        self._price = price
        self._orders = {}

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

    def add_order(self, order_id, qty):
        self._orders[order_id] = qty

    def change_order(self, order_id, qty):
        self._orders[order_id] = qty

    def remove_order(self, order_id):
        self._orders.pop(order_id, None)


class OrderBasedBook:
    def __init__(self, book_id):
        self._bids = SortedDict(key=lambda lvl: lvl.price)
        self._asks = SortedDict(key=lambda lvl: -lvl.price)

    def add_order(self, side, order_id, price, qty):
        lvl = self._fetch_level(side, price)
        lvl.add_order(order_id, qty)

    def change_order(self, side, order_id, price, qty):
        lvl = self._fetch_level(side, price)
        lvl.change_order(order_id, qty)

    def remove_order(self, side, order_id, price):
        lvl = self._fetch_level(side, price)
        lvl.remove_order(order_id)
        if lvl.empty:
            self._remove_level(side, price)

    def clear(self):
        self._bids.clear()
        self._asks.clear()

    def make_book(self, book_id):
        """Return market_data.Book for OrderBasedBook."""
        return Book(
                book_id=book_id,
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
            levels[price] = _OrderBasedLevel(price=price)
        return levels[price]
