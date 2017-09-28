from datetime import datetime
import decimal
import json

from convex.common import Instrument


def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""

    if isinstance(obj, (datetime)):
        return obj.isoformat()
    elif isinstance(obj, (Instrument)):
        return obj.__repr__()
    elif isinstance(obj, decimal.Decimal):
        return float(obj)
    raise TypeError('Type %s not serializable' % type(obj))


def to_json(msg):
    return json.dumps(msg,
                      sort_keys=True,
                      indent=4,
                      separators=(',', ': '),
                      default=json_serial)
