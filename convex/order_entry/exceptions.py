class OrderError(RuntimeError):
    """Base order entry error."""
    def __init__(self, order, reason=''):
        super().__init__(reason)
        self.order = order
        self.reason = reason


class SubmitNack(OrderError):
    """Exception raised for errors in submitting order."""
    def __init__(self, reason=''):
        super().__init__(None, reason)


class ReviseNack(OrderError):
    """Exception raised for errors in revising order."""
    def __init__(self, order, reason=''):
        super().__init__(order, reason)


class CancelNack(OrderError):
    """Exception raised for errors in canceling order."""
    def __init__(self, order, reason=''):
        super().__init__(order, reason)


class InternalNack(OrderError):
    """Exception raised for interal errors (e.g. limits)."""
    def __init__(self, order, reason=''):
        super().__init__(order, reason)
