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

    def show(self, concise=True):
        out = ''
        DEFAULT_LVL = Level(price='', qty='', orders='')
        BID_FMT = '{lvl.orders:3} {lvl.qty:10.5} {lvl.price:10.5}'
        ASK_FMT = '{lvl.price:10.5} {lvl.qty:10.5} {lvl.orders:3}'
        for bid, ask in itertools.zip_longest(
                self._bids, self._asks,
                fillvalue=DEFAULT_LVL):
            side_str = BID_FMT.format(lvl=bid) + ' | ' \
                    + ASK_FMT.format(lvl=ask)
            if concise:
                return '({}) '.format(self._book_id) + side_str
            out += side_str
        return out

    def __repr__(self):
        return self.show(concise=True)
