class OrderEventHandler:
    """Order event handler interface."""
    def on_fill(self, order, filled_qty):
        """Order was partially or fully filled."""
        pass

    def on_complete(self, order):
        """Order is no longer open."""
        pass
