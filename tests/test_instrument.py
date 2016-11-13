import pytest

from convex.common import Instrument
from convex.exchanges import ExchangeID


def test_from_string():
    s = 'BTCUSD@GDAX'
    inst = Instrument.from_string(s)
    assert inst.base_currency == 'BTC'
    assert inst.quote_currency == 'USD'
    assert inst.exchange_id == ExchangeID.GDAX


def test_from_string_invalid_base():
    s = 'UNKUSD@GDAX'
    with pytest.raises(ValueError):
        Instrument.from_string(s)
