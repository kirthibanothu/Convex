from collections import namedtuple


Trade = namedtuple('Trade', ['aggressor', 'price', 'qty', 'sequence'])
def dump_trade(trade):
    # The following conversions are necessary for using json dumps.
    return {
               'price': float(trade.price),
               'qty': float(trade.qty),
               'sequence': trade.sequence,
               'aggressor': str(trade.aggressor)
           }

