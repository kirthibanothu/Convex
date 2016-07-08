import itertools


class Level:
    __slots__ = '_price', '_qty', '_orders'

    def __init__(self, price, qty, orders=0):
        self._price = price
        self._qty = qty
        self._orders = orders

    @property
    def price(self):
        return self._price

    @property
    def qty(self):
        return self._qty

    @property
    def orders(self):
        return self._orders


class Book:
    __slots__ = '_bids', '_asks', '_book_id'

    def __init__(self, book_id, bids, asks):
        self._bids = bids if bids else []
        self._asks = asks if asks else []
        self._book_id = book_id

    @property
    def book_id(self):
        return self._book_id

    @property
    def bids(self):
        return self._bids

    @property
    def asks(self):
        return self._asks

    def show(self, max_depth=5):
        out = ''
        DEFAULT_LVL = Level(price='', qty='', orders='')
        BID_FMT = '{lvl.orders:3}  {lvl.qty:10} {lvl.price:10}'
        ASK_FMT = '{lvl.price:10} {lvl.qty:10}  {lvl.orders:3}'

        level_iter = itertools.zip_longest(
                self._bids, self._asks,
                fillvalue=DEFAULT_LVL)

        for depth, (bid, ask) in enumerate(level_iter):
            side_str = BID_FMT.format(lvl=bid) + ' | ' \
                    + ASK_FMT.format(lvl=ask)
            if max_depth == 0:
                return '({}) '.format(self._book_id) + side_str
            out += side_str + '\n'
            if depth >= max_depth:
                break
        return out

    def __repr__(self):
        return self.show(max_depth=0)
