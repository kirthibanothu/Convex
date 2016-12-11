class Context:
    """Empty class meant to contain arbitrary data."""
    def __init__(self, **kwargs):
        for (k, v) in kwargs.items():
            setattr(self, k, v)

    def to_dict(self):
        """Make recursive dictionary representation of context."""
        return {k: Context._to_dict_impl(v) for k, v in vars(self).items()}

    def __repr__(self):
        return str(self.to_dict())

    @staticmethod
    def _to_dict_impl(obj):
        try:
            return obj.to_dict()
        except AttributeError:
            return obj
