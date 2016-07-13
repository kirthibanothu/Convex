import pytest

from convex.market_data import OrderBasedBook
from convex.common import Side

ASK, BID = Side.ASK, Side.BID


@pytest.fixture
def book():
    return OrderBasedBook()


def test_empty(book):
    b = book.make_book(book_id=1)
    assert(len(b.asks) == 0)
    assert(len(b.bids) == 0)


def test_add(book):
    OID = 'abcdefg'
    book.add_order(side=ASK, order_id=OID, price=5, qty=10)
    b = book.make_book(book_id=1)
    assert b.bid_depth == 0
    assert b.ask_depth == 1
    level = b.best_ask

    assert level.orders == 1
    assert level.price == 5
    assert level.qty == 10
    orders = level.orders_view()
    assert len(orders) == 1
    assert orders[OID] == 10


def test_change(book):
    OID = 'abcdefg'
    book.add_order(side=ASK, order_id=OID, price=5, qty=7)
    book.change_order(side=ASK, order_id=OID, price=5, new_qty=3)

    b = book.make_book(book_id=0)

    level = b.best_ask
    assert level.orders == 1
    assert level.price == 5
    assert level.qty == 3


def test_match(book):
    OID = 'abcdefg'
    book.add_order(side=ASK, order_id=OID, price=5, qty=10)

    # Match half of the order
    book.match_order(side=ASK, order_id=OID, price=5, trade_qty=5)
    b = book.make_book(book_id=0)
    level = b.best_ask
    assert level.qty == 5

    # Match remaining quantity of the order
    book.match_order(side=ASK, order_id=OID, price=5, trade_qty=5)
    b = book.make_book(book_id=1)
    assert b.ask_depth == 0


def test_remove(book):
    OID = 'abcdefg'
    book.add_order(side=ASK, order_id=OID, price=5, qty=7)
    book.remove_order(side=ASK, order_id=OID, price=5)

    b = book.make_book(book_id=0)
    assert b.ask_depth == 0


def test_add_ordering(book):
    book.add_order(side=ASK, order_id=1, price=7, qty=8)
    book.add_order(side=ASK, order_id=2, price=7, qty=8)
    book.add_order(side=ASK, order_id=3, price=7, qty=8)

    b = book.make_book(book_id=0)
    order_ids = b.best_ask.orders_view().keys()
    for i, order_id in enumerate(order_ids):
        assert order_id == i + 1


def test_side_ordering(book):
    book.add_order(side=ASK, order_id=1, price=7, qty=8)
    book.add_order(side=ASK, order_id=2, price=6, qty=6)
    book.add_order(side=BID, order_id=3, price=4, qty=5)
    book.add_order(side=BID, order_id=4, price=5, qty=5)
    book.add_order(side=BID, order_id=5, price=4, qty=9)

    b = book.make_book(book_id=0)
    ask, bid = b.best_ask, b.best_bid
    assert ask.orders == 1
    assert bid.orders == 1
    assert bid.price == 5
    assert ask.price == 6
