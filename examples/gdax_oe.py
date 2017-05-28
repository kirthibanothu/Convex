#!/usr/bin/env python3
"""GDAX Order Entry Example Script

Usage:
    ./gdax_oe.py <API_KEY> <API_SECRET> <PASSPHRASE>
"""

import docopt
import logbook
import asyncio

from convex.common.app import AsyncApp
from convex.common import Instrument, Side, make_price, make_qty

from convex.order_entry.session import Session
from convex.order_entry import exceptions as oe_exceptions
from convex.order_entry.limit_checker import LimitChecker
from convex.exchanges import gdax

log = logbook.Logger('EXAMPLE')


class Example:
    def __init__(self, gateway, instrument):
        limits = LimitChecker(max_order_qty=make_qty('0.8'),
                              max_order_value=make_price('200.50'),
                              max_open_value=200)
        self.session = Session(gateway=gateway,
                               instrument=instrument,
                               limits=limits)
        self.session.add_event_handler(self)

    def on_fill(self, order, filled_qty):
        log.info('Order filled: filled_qty={}, order={}', filled_qty, order)

    def on_complete(self, order):
        log.info('Order completed: order={}', order)

    async def check_balance(self):
        base, quote = await self.session.get_balances()
        log.info('Balances: base={}, quote={}', base, quote)

    async def run(self):
        await self.session.wait_ready()
        order = await self.submit_order(
                side=Side.BUY,
                price=make_price(300),
                qty=make_qty('0.50'))
        log.info('Submitted: order={}', order)

        await asyncio.sleep(3)

        ioc = await self.submit_ioc(
                side=Side.BUY,
                price=make_price(1000),
                qty=make_qty('0.02'))
        log.info('Submitted IOC: order={}', ioc)

        await asyncio.sleep(3)

        try:
            if order is not None:
                await order.cancel()
        except oe_exceptions.CancelNack as cnack:
            log.error('{}: {}', cnack.order, cnack)

        await self.check_balance()

    async def submit_order(self, **kwargs):
        try:
            order = await self.session.submit(**kwargs)
            await self.check_balance()
            return order
        except oe_exceptions.SubmitNack as nack:
            log.error(nack)

    async def submit_ioc(self, **kwargs):
        try:
            order = await self.session.submit_ioc(**kwargs)
            await self.check_balance()
            return order
        except oe_exceptions.SubmitNack as nack:
            log.error(nack)


def main(args):
    app = AsyncApp(name='gdax_oe_example')

    gateway = gdax.OrderEntryGateway(
            api_url=gdax.OrderEntryGateway.SANDBOX_URL,
            api_key=args['<API_KEY>'],
            secret_key=args['<API_SECRET>'],
            passphrase=args['<PASSPHRASE>'],
            loop=app.loop)

    instrument = Instrument.from_string('BTCUSD@GDAX')

    example = Example(gateway=gateway, instrument=instrument)

    app.add_run_callback(gateway.launch, shutdown_cb=gateway.shutdown)
    app.add_run_callback(example.run)
    app.run()

if __name__ == '__main__':
    args = docopt.docopt(__doc__)
    main(args)
