from logger import log

from convex.order_entry.session import Session
from convex.order_entry.limit_checker import LimitChecker
from convex.order_entry import exceptions as oe_exceptions


def construct_error(action, args=''):
    return {'msg': action, 'args': args}


class Trader:
    def __init__(self, gateway, instrument, limits):
        limits = LimitChecker(limits['max_order_qty'],
                              limits['max_order_value'],
                              limits['max_open_value'])
        self._session = Session(gateway, instrument, limits)

    async def get_balance(self):
        base, quote = await self._session.get_balances()
        return {
                   'base': {
                       'available': base['available'],
                       'hold': base['hold']
                   },
                   'quote': {
                       'available': quote['available'],
                       'hold': quote['hold']
                   }
               }

    # Log Helpers
    async def _log_ack(self, msg_type, order):
        log.info('Submitted order for {}', str(order))

    async def _log_orders(self):
        orders = await self._session.exch_orders()

        open_orders = ""
        for o in orders:
            open_orders = " " + str(o.price) + ", " + \
                str(o.remaining_qty) + ", " + str(o.original_qty) + "|"

        log.info('Open Orders: {}', open_orders)

    async def _log_balance(self):
        balance = await self.get_balance()
        log.info(
            'Balances: base=avail:{}|hold:{}, quote=avail:{}|hold:{}',
            balance['base']['available'], balance['base']['hold'],
            balance['quote']['available'], balance['quote']['hold'])

    def _log_error(self, error_type, error, trigger):
        log.error(error)
        msg = {'error': str(error), 'trigger': trigger}
        log.info('Error Msg: [{}] {}', error_type, msg)

    # Order Actions
    async def submit_order(self, **kwargs):
        try:
            order = await self._session.submit(**kwargs)

            if (order):
                await self._log_ack("submit_ack", order.dump())
            return order
        except oe_exceptions.SubmitNack as e:
            self._log_error('submit_nack', e, construct_error('submit'))
        except oe_exceptions.LimitError as e:
            self._log_error('limit_error', e, construct_error('submit'))
        except oe_exceptions.InternalNack as e:
            self._log_error('internal_nack', e, construct_error('submit'))
        except oe_exceptions.OrderError as e:
            self._log_error('order_error', e, construct_error('submit'))
        except Exception as e:
            log.exception('Unhandled err [{}] when trying to submit order.', e)

    async def submit_ioc(self, **kwargs):
        try:
            order = await self._session.submit_ioc(**kwargs)

            if (order):
                await self._log_ack("submit_ack", order.dump())

            return order
        except oe_exceptions.SubmitNack as e:
            self._log_error('submit_nack', e, construct_error('submit_ioc'))
        except oe_exceptions.LimitError as e:
            self._log_error('limit_error', e, construct_error('submit_ioc'))
        except oe_exceptions.InternalNack as e:
            self._log_error('internal_nack', e, construct_error('submit_ioc'))
        except oe_exceptions.OrderError as e:
            self._log_error('order_error', e, construct_error('submit_ioc'))
        except Exception as e:
            log.exception('Unhandled err [{}] when trying to submit order.', e)

    async def cancel_order(self, order):
        try:
            await self._session.cancel(order)
        except oe_exceptions.CancelNack as nack:
            self._log_error(
                'cancel_nack', nack, construct_error('cancel_order', order))
        except Exception as e:
            log.exception('Unhandled err [{}] when trying to cancel order.', e)

    async def cancel_session(self):
        try:
            await self._session.cancel_session()
            await self._log_balance()
            await self._log_orders()

        except oe_exceptions.CancelNack as e:
            self._log_error(
                'cancel_nack', e, construct_error('cancel_session'))
        except Exception as e:
            log.exception(
                'Unhandled err [{}] when trying to cancel session.', e)

    async def cancel_all(self):
        try:
            await self._session.cancel_all()
            await self._log_balance()
            await self._log_orders()

        except oe_exceptions.CancelNack as nack:
            self._log_error(
                'cancel_all_nack', nack, construct_error('cancel_all'))
        except Exception as e:
            log.exception('Unhandled err [{}] when trying to cancel all.', e)
