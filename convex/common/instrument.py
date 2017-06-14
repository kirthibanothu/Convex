from ..exchanges import ExchangeID

class Instrument:
    DEFAULT_SEPERATOR = ''
    KNOWN_CURRENCiES = 'USD', 'BTC', 'LTC', 'ETH'
    SYMBOL_FMT = '{base}{quote}@{exch}'

    __slots__ = '_base_currency', '_quote_currency', '_exchange_id'

    def __init__(self, base_currency, quote_currency, exchange_id):
        self._base_currency = base_currency.upper()
        self._quote_currency = quote_currency.upper()
        self._exchange_id = exchange_id

    @staticmethod
    def from_string(s):
        """Create instrument from string.

        Args:
            s (str): String of form AAABBB@CCC

        Returns:
            Instrument
        """
        pair, exchange = s.split('@')
        base = pair[:3]
        quote = pair[3:]
        if base not in Instrument.KNOWN_CURRENCiES:
            raise ValueError('Unknown base currency: {}'.format(base))
        if quote not in Instrument.KNOWN_CURRENCiES:
            raise ValueError('Unknown quote currency: {}'.format(quote))

        return Instrument(base_currency=base,
                          quote_currency=quote,
                          exchange_id=ExchangeID[exchange])

    @property
    def base(self):
        return self._base_currency

    @property
    def base_currency(self):
        return self._base_currency

    @property
    def quote(self):
        return self._quote_currency

    @property
    def quote_currency(self):
        return self._quote_currency

    @property
    def exchange_id(self):
        return self._exchange_id

    def __eq__(self, other):
        return self._key() == other._key()

    def __ne__(self, other):
        return not self.__eq__(other)

    def __str__(self):
        return Instrument.SYMBOL_FMT.format(
                base=self._base_currency,
                quote=self._quote_currency,
                exch=self._exchange_id.name)

    def __hash__(self):
        return hash(self._key())

    def __repr__(self):
        return self.__str__()

    def _key(self):
        """Return key for comparison and hashing."""
        return self._base_currency, self._quote_currency

def make_btc_usd(exchange_id):
    """Return BTC/USD Instrument for given exchange."""
    return Instrument(base_currency='BTC',
                      quote_currency='USD',
                      exchange_id=exchange_id)

def make_ltc_usd(exchange_id):
    """Return LTC/USD Instrument for given exchange."""
    return Instrument(base_currency='LTC',
                      quote_currency='USD',
                      exchange_id=exchange_id)

def make_eth_usd(exchange_id):
    """Return ETH/USD Instrument for given exchange."""
    return Instrument(base_currency='ETH',
                      quote_currency='USD',
                      exchange_id=exchange_id)


