import logbook

from .exceptions import LimitError

log = logbook.Logger('LIMIT')


class LimitChecker:
    def __init__(self,
                 max_order_qty,
                 max_order_value,
                 max_open_value):
        self.max_order_qty = max_order_qty
        self.max_order_value = max_order_value
        self.max_open_value = max_open_value

    def check_submit(self, side, price, qty, open_orders):
        qty = min(qty, self.max_order_qty)
        cash_risk = price * qty
        if cash_risk > self.max_order_value:
            raise LimitError('Order value breach: ' +
                             'value={}, limit={}'.format(
                                 cash_risk, self.max_order_value))

        def cash_value(order): return order.price * order.remaining_qty

        open_value = sum(map(cash_value, open_orders))

        if cash_risk + open_value > self.max_open_value:
            raise LimitError('Open cash value breach: ' +
                             'value={}, limit={}'.format(
                                 open_value + cash_risk, self.max_open_value))
        return side, price, qty

    @staticmethod
    def submit_check(submit_func):
        async def submit_wrapper(session, side, price, qty, **kwargs):
            log.notice('Check limits')
            side, price, qty = session.limits.check_submit(side,
                                                           price,
                                                           qty,
                                                           session.open_orders)
            return await submit_func(session, side, price, qty, **kwargs)
        return submit_wrapper
