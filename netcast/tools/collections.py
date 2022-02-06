from __future__ import annotations

from typing import Callable

from jaraco.collections import (
    KeyTransformingDict as _KeyTransformingDict,
    ItemsAsAttributes,
)


class KeyTransformingDict(_KeyTransformingDict):
    def update(self, e=None, **f):
        d = self
        if e:
            if callable(getattr(e, "keys", None)):
                for k in e:
                    d[k] = e[k]
            else:
                for k, v in e:
                    d[k] = v
        for k in f:
            d[k] = f[k]


class IDLookupDictionary(KeyTransformingDict):
    """
    A dictionary that uses id() for storing and lookup.
    """
    _ref = {}

    def restore_key(self, key):
        return self._ref.pop(key)

    def transform_key(self, key):
        id_of_key = id(key)
        self._ref[id_of_key] = key
        return id_of_key


class OrOperatorDict(dict):
    def __or__(self, other):
        """Return self | other."""
        return type(self).__ior__(self.copy(), other)  # type: ignore

    def __ior__(self, other):
        """Return self |= other."""
        self.update(other)
        return self


class AttributeDict(OrOperatorDict, ItemsAsAttributes):
    """A modern dictionary with attribute-as-item access."""

    def __setattr__(self, key, value):
        """self[key] = value, but via attribute setting"""
        self.__setitem__(key, value)

    def __dir__(self):
        """List all accessible names bound to this object."""
        return list(self.keys())


class Params:
    _args: tuple | Callable = ()
    _kwargs: dict | Callable = {}

    def __init__(self, args=None, kwargs=None):
        if args is not None:
            self._args = args
        if kwargs is not None:
            self._kwargs = kwargs

    def __iter__(self):
        yield from (self.args, self.kwargs)

    @classmethod
    def frame(cls, *args, **kwargs):
        return cls(args=args, kwargs=kwargs)

    @property
    def args(self) -> tuple | Callable:
        return self._args

    @property
    def kwargs(self) -> dict | Callable:
        return self._kwargs


class ForwardDependency:
    def __init__(self, dependent_class=None, unbound=None):
        self.__dependent_class = None
        self.__cache = IDLookupDictionary()
        self.__unbound = unbound

        self.dependency(dependent_class)

    def dependency(self, dependent_class=None):
        if self.__dependent_class is not None:
            raise TypeError("dynamic dependency already bound")
        self.__dependent_class = dependent_class
        return dependent_class

    def __get__(self, instance, owner):
        if instance is None:
            return self
        if instance not in self.__cache:
            if self.__unbound is None:
                # pylint: disable=CO415
                from netcast.tools.arrangements import Arrangement

                unbound = issubclass(type(instance), Arrangement)
            else:
                unbound = self.__unbound
            self.__cache[instance] = (
                self.__dependent_class(instance)
                if unbound
                else self.__dependent_class()
            )
        return self.__cache[instance]


class ClassProperty(classmethod):
    def __get__(self, instance, owner=None):
        if instance is None:
            cls = owner
        else:
            cls = type(instance)
        return self.__func__(cls)


classproperty = ClassProperty  # pylint: disable=C0103
