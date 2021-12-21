from __future__ import annotations
from collections import UserList
from collections.abc import MutableSet

from jaraco.collections import KeyTransformingDict as _KeyTransformingDict, ItemsAsAttributes


class ModernDict(dict):
    def __or__(self, other):
        """Return self | other."""
        return type(self).__ior__(self.copy(), other)  # type: ignore

    def __ior__(self, other):
        """Return self |= other."""
        self.update(other)
        return self


class KeyTransformingDict(_KeyTransformingDict):
    def update(self, e=None, **f):
        """
        D.update([E, ]**F) -> None.  Update D from dict/iterable E and F.
        If E is present and has a .keys() method, then does:  for k in E: D[k] = E[k]
        If E is present and lacks a .keys() method, then does:  for k, v in E: D[k] = v
        In either case, this is followed by: for k in F:  D[k] = F[k]
        """  # copied from builtins
        # Somebody forgot that update() doesn't call the public __setitem__() method…
        # …or it's a pesky bug. IDK, according to the docs that magic method should be called then.
        # So, to make things work, I just turned the docs into the code below.
        d = self
        if e and e is not None:
            if callable(getattr(e, 'keys', None)):
                for k in e:
                    d[k] = e[k]
            else:
                for k, v in e:
                    d[k] = v
        for k in f:
            d[k] = f[k]


class MemoryDict(KeyTransformingDict):
    """
    A dictionary for storing information about Python objects without comparing themselves,
    but their ID.  Keys don't have to be hashable, because only their place in memory is stored.

    Examples
    --------
    >>> memory_dict = MemoryDict()
    >>> a = []
    >>> b = []
    >>> a == b
    True
    >>> memory_dict[a] = 0
    >>> memory_dict[a]
    0
    >>> memory_dict[b]
    Traceback (most recent call last):
    ...
    KeyError: ...
    """
    transform_key = id


class AttributeDict(ModernDict, ItemsAsAttributes):
    """A modern dictionary with attribute-as-item access."""

    def __setattr__(self, key, value):
        """self[key] = value, but via attribute setting"""
        self.__setitem__(key, value)

    def __dir__(self):
        """List all accessible names bound to this object."""
        return list(self.keys())


class ItemTransformingList(UserList):
    """
    A list that transforms each item before accepting it.
    No back transformation.
    """
    @staticmethod
    def transform_item(item):
        return item

    def transform_items(self, items):
        return type(self)(map(self.transform_item, items))

    def __lt__(self, other):
        other = self.transform_items(other)
        return super().__lt__(other)

    def __le__(self, other):
        other = self.transform_items(other)
        return super().__le__(other)

    def __eq__(self, other):
        other = self.transform_items(other)
        return super().__eq__(other)

    def __gt__(self, other):
        other = self.transform_items(other)
        return super().__gt__(other)

    def __ge__(self, other):
        other = self.transform_items(other)
        return super().__ge__(other)

    def __contains__(self, item):
        item = self.transform_item(item)
        return super().__contains__(item)

    def __setitem__(self, i, item):
        item = self.transform_item(item)
        return super().__setitem__(i, item)

    def __add__(self, other):
        other = self.transform_items(other)
        return super().__add__(other)

    def __radd__(self, other):
        other = self.transform_items(other)
        return super().__radd__(other)  # noqa

    def __iadd__(self, other):
        other = self.transform_items(other)
        return super().__iadd__(other)

    def append(self, item):
        item = self.transform_item(item)
        return super().append(item)

    def insert(self, i, item):
        item = self.transform_item(item)
        return super().insert(i, item)

    def remove(self, item):
        item = self.transform_item(item)
        return super().remove(item)

    def count(self, item):
        item = self.transform_item(item)
        return super().count(item)

    def index(self, item, *args):
        item = self.transform_item(item)
        return super().index(item, *args)

    def extend(self, other):
        other = map(self.transform_item, other)
        return super().extend(other)


class ItemTransformingSet(set):
    """
    A set that transforms each item before accepting it.
    No back transformation.
    """

    @staticmethod
    def transform_item(item):
        return item

    def add(self: set | "ItemTransformingSet", value):
        value = self.transform_item(value)
        set.add(self, value)

    def discard(self: set | "ItemTransformingSet", value):
        value = self.transform_item(value)
        set.discard(self, value)


class MemoryList(ItemTransformingList):
    """A list for storing Python object ids."""
    transform_item = id

    def transform_items(self, items):
        if isinstance(items, type(self)):
            return items
        return super().transform_items(items)


class MemorySet(ItemTransformingSet):
    """A list for storing Python object ids."""
    transform_item = id
