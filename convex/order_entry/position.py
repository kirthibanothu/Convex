from convex.common import make_price, make_qty


class Position:
    """Account Position."""
    def __init__(self, instrument):
        self._instrument = instrument
        self.open_long = make_qty(0)
        self.open_short = make_qty(0)
        self.base_amount = make_qty(0)
        self.quote_amount = make_price(0)

    @property
    def instrument(self):
        """Instrument."""
        return self._instrument

    @property
    def exchange_id(self):
        """Exchange ID."""
        return self._instrument.exchange_id

    def __repr__(self):
        c = '{x.instrument}: {x.base_amount}/{x.quote_amount}, '.format(x=self)
        return c + 'long: {x.open_long}, short: {x.open_short}'.format(x=self)
