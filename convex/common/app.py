import asyncio
import signal
import os

import logbook
import uvloop

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

log = logbook.Logger('APP')


class AsyncApp:
    """Base async application."""
    LOG_FORMAT = (
        '{record.time:%Y-%m-%d %H:%M:%S.%f} - ' +
        '{record.module} - ' +
        '{record.level_name} - ' +
        '{record.message}'
    )

    def __init__(self, name, loop=None):
        self._name = name
        self._log_handler = logbook.TimedRotatingFileHandler(
                '{}-p{}.log'.format(name, os.getpid()),
                format_string=AsyncApp.LOG_FORMAT)
        self._loop = loop if loop else asyncio.get_event_loop()
        self._loop.add_signal_handler(signal.SIGINT, self._on_sigint)
        self._run_cbs = set()
        self._shutdown_cbs = set()

    @property
    def loop(self):
        """Event loop."""
        return self._loop

    def add_run_callback(self, cb, shutdown_cb=None):
        """Add callback to be run when app is started.

        Args:
            cb (coroutine): Callback to be run
            shutdown_cb (function): Shutdown callback
        """
        self._run_cbs.add(cb)
        if shutdown_cb:
            self.add_shutdown_callback(shutdown_cb)

    def add_shutdown_callback(self, cb):
        """Add callback to be run on SIGINT.

        Callback is called exactly once.

        Args:
            cb (function): Shutdown callback
        """
        if asyncio.iscoroutine(cb) or asyncio.iscoroutinefunction(cb):
            raise ValueError('Shutdown callback is coroutine')
        self._shutdown_cbs.add(cb)

    def run(self):
        """Start app."""
        with self._log_handler.applicationbound():
            log.info('Running AsyncApp, name={}', self._name)
            log.info('Running event loop with {} task(s)', len(self._run_cbs))
            coros = [AsyncApp._convert_coroutine(cb) for cb in self._run_cbs]
            del self._run_cbs
            tasks = asyncio.gather(*coros)
            asyncio.ensure_future(tasks, loop=self._loop)
            try:
                self._loop.run_forever()
            except asyncio.CancelledError:
                log.notice('Tasks have been canceled')
            except:
                log.exception()
            finally:
                self._stop_loop()

    @staticmethod
    def _convert_coroutine(cb):
        if asyncio.iscoroutine(cb):
            return cb
        return cb()

    def _stop_loop(self):
        if self._loop.is_running():
            log.notice('Stopping event loop')
            self._loop.stop()
        else:
            log.notice('Event loop already stopped')

    def _cancel_all(self):
        log.notice('Cancelling tasks')
        task_count = 0
        for task in asyncio.Task.all_tasks(loop=self._loop):
            task_count += 1
            task.cancel()
        log.notice('Cancelled {} task(s)', task_count)

    def _on_sigint(self):
        log.notice('Caught {sig.name}:{sig.value}', sig=signal.SIGINT)
        if self._shutdown_cbs:
            for cb in self._shutdown_cbs:
                cb()
            self._shutdown_cbs = None
            return
        self._stop_loop()
        self._cancel_all()
