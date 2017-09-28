import logbook
import sys

LOG_FORMAT = '{record.time:%Y-%m-%d %H:%M:%S.%f}: {record.level_name} | ' \
             '{record.message} | {record.module}| {record.func_name} ' \
             '{record.filename}:{record.lineno}'

logbook.StreamHandler(
    sys.stderr,
    level='INFO',
    bubble=True,
    format_string=LOG_FORMAT).push_application()
logbook.FileHandler(
    'anchor.log',
    level='DEBUG',
    format_string=LOG_FORMAT,
    bubble=True).push_application()

log = logbook.Logger('Strategy')

