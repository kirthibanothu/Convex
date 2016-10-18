import asyncio


class Pending:
    """Pending value.

    Wraps asyncio.Event
    """
    def __init__(self):
        self._event = asyncio.Event()
        self._exception = None

    def set(self, value):
        """Set value."""
        self._value = value
        self._event.set()

    def set_exception(self, e):
        """Set exception."""
        self._exception = e
        self._event.set()

    def clear(self):
        """Clear value and exception."""
        self._exception = None
        try:
            del self._value
        except AttributeError:
            pass
        self._event.clear()

    async def result(self):
        """Return pending value.

        Raises exception if one was set.

        This method is a coroutine.
        """
        if not self._event.is_set():
            await self._event.wait()
        if self._exception:
            raise self._exception
        return self._value
