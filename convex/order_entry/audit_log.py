import os

import logbook


class AuditLog:
    LOG_FORMAT = '{record.time:%Y-%m-%d %H:%M:%S.%f}: {record.message}'

    def __init__(self, exchange_id):
        handler = logbook.FileHandler(
                '{}-p{}.audit'.format(exchange_id.name, os.getpid()),
                format_string=AuditLog.LOG_FORMAT)

        self._logger = logbook.Logger(exchange_id.name)
        self._logger.handlers.append(handler)

    def incoming(self, fmt, *args, **kwargs):
        fmt = fmt if isinstance(fmt, str) else str(fmt)
        self._logger.info('<-- ' + fmt, *args, **kwargs)

    def outgoing(self, fmt, *args, **kwargs):
        fmt = fmt if isinstance(fmt, str) else str(fmt)
        self._logger.info('--> ' + fmt, *args, **kwargs)
