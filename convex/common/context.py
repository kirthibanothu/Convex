class Context:
    """Empty class meant to contain arbitrary strategy data."""
    def __init__(self, **kwargs):
        for (k, v) in kwargs.items():
            setattr(self, k, v)

    def __repr__(self):
        return str(self.__dict__)
