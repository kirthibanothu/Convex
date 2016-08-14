class Instrument:
    DEFAULT_SEPERATOR = '/'

    __slots__ = '_base_currency', '_quote_currency', '_exchange_id'

    def __init__(self, base_currency, quote_currency, exchange_id):
        self._base_currency = base_currency.upper()
        self._quote_currency = quote_currency.upper()
        self._exchange_id = exchange_id

    @property
    def base_currency(self):
        return self._base_currency

    @property
    def quote_currency(self):
        return self._quote_currency

    @property
    def exchange_id(self):
        return self._exchange_id

    def make_symbol(self, seperator=DEFAULT_SEPERATOR):
        curr = seperator.join([self._base_currency, self._quote_currency])
        return '{}::{}'.format(self._exchange_id.name, curr)

    def __eq__(self, other):
        return self._key() == other._key()

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash(self._key())

    def __repr__(self):
        return self.make_symbol()

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
