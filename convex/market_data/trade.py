from collections import namedtuple


Trade = namedtuple('Trade', ['aggressor', 'price', 'qty', 'sequence', 'maker_id', 'taker_id', 'time'])


def dump_trade(trade):
    # The following conversions are necessary for using json dumps.
    return {
        'price': str(trade.price),
        'qty': str(trade.qty),
        'sequence': trade.sequence,
        'aggressor': str(trade.aggressor),
        'maker_order_id': trade.maker_id,
        'taker_order_id': trade.taker_id,
        'time': str(trade.time)
    }
