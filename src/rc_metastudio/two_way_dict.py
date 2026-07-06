"""Dictionary with reverse lookup support."""

from copy import deepcopy


class TwoWayDict(dict):
    """A one-to-one dictionary that can also look up keys by value."""

    def __init__(self, *args, **kwargs):
        self._reverse_map = {}
        super().__init__()
        self.update(*args, **kwargs)

    def __setitem__(self, key, value):
        if value in self._reverse_map:
            del self[self._reverse_map[value]]
        if key in self:
            del self._reverse_map[self[key]]
        self._reverse_map[value] = key
        super().__setitem__(key, value)

    def __delitem__(self, key):
        value = self[key]
        del self._reverse_map[value]
        super().__delitem__(key)

    def __deepcopy__(self, memo):
        duplicate = self.__class__()
        memo[id(self)] = duplicate
        for key, value in self.items():
            duplicate[deepcopy(key, memo)] = deepcopy(value, memo)
        return duplicate

    def copy(self):
        return self.__class__(self)

    def __reduce__(self):
        return (self.__class__, (dict(self),))

    def clear(self):
        super().clear()
        self._reverse_map.clear()

    def key(self, value):
        return self._reverse_map[value]

    def get_key(self, value, default=None):
        return self._reverse_map.get(value, default)

    def reversed_items(self):
        return list(self._reverse_map.items())

    def pop(self, key, *args):
        try:
            value = self[key]
        except KeyError:
            if not args:
                raise
            return args[0]
        del self[key]
        return value

    def popitem(self):
        key, value = super().popitem()
        del self._reverse_map[value]
        return key, value

    def update(self, other=None, **kwargs):
        if other is not None:
            for key, value in dict(other).items():
                self[key] = value
        for key, value in kwargs.items():
            self[key] = value

    @classmethod
    def fromkeys(cls, iterable, value=None):
        mapping = cls()
        for key in iterable:
            mapping[key] = value
        return mapping
