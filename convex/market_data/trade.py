from collections import namedtuple


Trade = namedtuple('Trade', ['aggressor', 'price', 'qty', 'sequence'])


def dump_trade(trade):
    # The following conversions are necessary for using json dumps.
    return {
        'price': str(trade.price),
        'qty': str(trade.qty),
        'sequence': trade.sequence,
        'aggressor': str(trade.aggressor)
    }
