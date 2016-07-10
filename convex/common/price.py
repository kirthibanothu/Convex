import decimal

_PRICE_CONTEXT = decimal.Context(prec=16)
_QTY_CONTEXT = decimal.Context(prec=16)

make_price = _PRICE_CONTEXT.create_decimal
make_qty = _QTY_CONTEXT.create_decimal
