class OrderError(RuntimeError):
    """Base order entry error."""
    def __init__(self, order, reason=''):
        super().__init__(reason)
        self.order = order
        self.reason = reason


class SubmitNack(OrderError):
    """Exception raised for errors in submitting order."""
    def __init__(self, order, reason=''):
        super().__init__(order, reason)


class ReviseNack(OrderNack):
    """Exception raised for errors in revising order."""
    def __init__(self, order, reason=''):
        super().__init__(order, reason)


class CancelNack(OrderNack):
    """Exception raised for errors in canceling order."""
    def __init__(self, order, reason=''):
        super().__init__(order, reason)


class InternalNack(OrderNack):
    """Exception raised for interal errors (e.g. limits)."""
    def __init__(self, order, reason=''):
        super().__init__(order, reason)
