from datetime import datetime
from decimal import Decimal
import json

from convex.common import Instrument


class PostOnlyException(Exception):
    pass


def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""

    if isinstance(obj, (datetime)):
        return obj.isoformat()
    elif isinstance(obj, (Instrument)):
        return obj.__repr__()
    elif isinstance(obj, Decimal):
        return float(obj)
    raise TypeError('Type %s not serializable' % type(obj))


def to_json(msg):
    return json.dumps(msg,
                      sort_keys=True,
                      indent=4,
                      separators=(',', ': '),
                      default=json_serial)


def simple_midpoint(book):
    bid = book['bids'][0]
    ask = book['asks'][0]
    total_qty = float(bid['qty'])+float(ask['qty'])

    weighted_bid = float(bid['price'])*float(ask['qty'])
    weighted_ask = float(ask['price'])*float(bid['qty'])
    return (weighted_bid + weighted_ask) / total_qty


def weighted_midpoint(book):
    bid_p = book.best_bid.price
    ask_p = book.best_ask.price

    bid_q = book.best_bid.qty
    ask_q = book.best_ask.qty

    return round((bid_p*ask_q + ask_p*bid_q)/(bid_q + ask_q), 8)


def is_valid_book(book):
    return (len(book['asks']) > 0 and
            len(book['bids']) > 0 and
            float(book['bids'][0]['qty']) > 0 and
            float(book['asks'][0]['qty']) > 0)
