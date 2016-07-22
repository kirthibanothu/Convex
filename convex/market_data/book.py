import itertools


class Level:
    __slots__ = '_price', '_qty', '_orders'

    def __init__(self, price, qty, orders=0):
        self._price = price
        self._qty = qty
        self._orders = orders

    @property
    def price(self):
        """Price"""
        return self._price

    @property
    def qty(self):
        """Quantity"""
        return self._qty

    @property
    def orders(self):
        """Number of orders"""
        return self._orders


class Book:
    __slots__ = '_bids', '_asks', '_book_id'

    def __init__(self, book_id, bids, asks):
        self._bids = bids if bids else []
        self._asks = asks if asks else []
        self._book_id = book_id

    @property
    def book_id(self):
        """Book ID.

        Indicates ordering of events pertaining to a single instrument on a
        given exchange.
        """
        return self._book_id

    @property
    def depth(self):
        """Book depth."""
        return max(self.bid_depth, self.ask_depth)

    @property
    def bid_depth(self):
        """Number of bid levels."""
        return len(self._bids)

    @property
    def ask_depth(self):
        """Number of ask levels."""
        return len(self._asks)

    @property
    def bids(self):
        """Bid levels."""
        return self._bids

    @property
    def asks(self):
        """Ask levels."""
        return self._asks

    @property
    def best_bid(self):
        """Best bid level."""
        return next(iter(self._bids))

    @property
    def best_ask(self):
        """Best ask level."""
        return next(iter(self._asks))

    def show(self, max_depth=5):
        """Return visual represention of book.

        Args:
            max_depth (int): Number of levels to display.
        """
        DEFAULT_LVL = Level(price='', qty='', orders='')
        BID_FMT = '{lvl.orders:3}  {lvl.qty:15} {lvl.price:12}'
        ASK_FMT = '{lvl.price:<12} {lvl.qty:<15}  {lvl.orders:<3}'

        level_iter = itertools.zip_longest(
                self._bids, self._asks,
                fillvalue=DEFAULT_LVL)

        out = ''
        if max_depth > 1:
            out += 'book_id={}, bid_depth={}, ask_depth={}\n'.format(
                    self._book_id,
                    len(self._bids),
                    len(self._asks))

        for depth, (bid, ask) in enumerate(level_iter):
            side_str = BID_FMT.format(lvl=bid) + ' | ' \
                    + ASK_FMT.format(lvl=ask)
            if max_depth <= 1:
                return '({}) '.format(self._book_id) + side_str
            out += side_str + '\n'
            if depth >= max_depth:
                break
        return out

    def __repr__(self):
        return self.show(max_depth=0)
