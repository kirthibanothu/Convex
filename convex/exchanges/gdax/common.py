GDAX_SYMBOL_FORMAT = '{inst.base_currency}-{inst.quote_currency}'


def make_symbol(instrument):
    return GDAX_SYMBOL_FORMAT.format(inst=instrument)
