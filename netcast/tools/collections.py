from __future__ import annotations  # Python 3.8

from typing import Any, Callable, Protocol, TypeVar, runtime_checkable

from netcast.constants import MISSING


@runtime_checkable
class Comparable(Protocol):
    def __lt__(self: _ComparableT, other: _ComparableT) -> bool | NotImplemented:
        """Return self < other."""


_ComparableT = TypeVar("_ComparableT", bound=Comparable)


class KeyTransformingDict(dict):
    @staticmethod
    def transform_key(key):  # pragma: nocover
        return key

    def __init__(self, *args, **kwargs):
        super().__init__()
        descent = dict(*args, **kwargs)
        for item in descent.items():
            self.__setitem__(*item)

    def __setitem__(self, key, val):
        key = self.transform_key(key)
        super().__setitem__(key, val)

    def __getitem__(self, key):
        key = self.transform_key(key)
        return super().__getitem__(key)

    def __contains__(self, key):
        key = self.transform_key(key)
        return super().__contains__(key)

    def __delitem__(self, key):
        key = self.transform_key(key)
        return super().__delitem__(key)

    def get(self, key, default=None):
        key = self.transform_key(key)
        return super().get(key, default)

    def setdefault(self, key, default=None):
        key = self.transform_key(key)
        return super().setdefault(key, default)

    def pop(self, key, default=MISSING):
        key = self.transform_key(key)
        if default is MISSING:
            return super().pop(key)
        return super().pop(key, default)

    # I don't know why update() doesn't internally call __setitem__(), either on CPython or PyPy
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

    _pointers: dict[int, Any] = {}

    def restore_key(self, key):
        return self._pointers.pop(key)

    def transform_key(self, key):
        id_of_key = id(key)
        self._pointers[id_of_key] = key
        return id_of_key


class AttributeDict(dict):
    """A dictionary with attribute-as-item access."""

    def __setattr__(self, key: str, value: Any):
        """self[key] = value, but via attribute setting"""
        self.__setitem__(key, value)

    def __getattr__(self, item: str):
        try:
            return self[item]
        except KeyError as e:
            raise AttributeError(
                f"{type(self).__name__!r} object has no attribute {item!r}"
            ) from e

    def __dir__(self):
        """List all accessible names bound to this object."""
        return list(self.keys())


class ParameterHolder:
    arguments: tuple | Callable = ()
    keywords: dict | Callable = {}

    def __init__(self, arguments=None, keywords=None):
        if arguments is not None:
            self.arguments = arguments
        if keywords is not None:
            self.keywords = keywords

    def eval(self, context):
        return self.eval_arguments(context), self.eval_keywords(context)

    def eval_arguments(self, context=MISSING):
        if callable(self.arguments):
            if context is MISSING:
                return self.arguments()
            return self.arguments(context)
        return self.arguments

    def eval_keywords(self, context=MISSING):
        if callable(self.keywords):
            if context is MISSING:
                return self.keywords()
            return self.keywords(context)
        return self.keywords

    @classmethod
    def unstar(cls, *arguments, **keywords):
        return cls(arguments=arguments, keywords=keywords)

    def __iter__(self):
        param_tuple = (self.arguments, self.keywords)
        yield from param_tuple

    def repr_arguments(self):
        if callable(self.arguments):
            return "<arguments factory>"
        return ", ".join(map(repr, self.arguments))

    def repr_keywords(self):
        if callable(self.keywords):
            return "<keyword arguments factory>"
        return ", ".join(
            map(
                lambda key_value: f"{key_value[0]}={key_value[1]!r}",
                self.keywords.items(),
            )
        )

    def __repr__(self):
        params = tuple(filter(None, (self.repr_arguments(), self.repr_keywords())))
        if not params:
            return "(no parameters)"
        return ", ".join(params).join("()")


parameters = ParameterHolder.unstar


class ForwardDependency:
    def __init__(
        self, dependent_class: type | None = None, bind: bool | None = None
    ):
        self.__dependent_class = None
        self.__cache = IDLookupDictionary()
        self.__bind = bind

        self.dependency(dependent_class)

    def dependency(self, dependent_class: type | None = None):
        if self.__dependent_class is not None:
            raise TypeError("dynamic dependency already bound")
        self.__dependent_class = dependent_class
        return dependent_class

    def __get__(self, instance: Any, owner: type | None):
        if instance is None:
            return self
        if instance not in self.__cache:
            unbound = self.__bind
            if unbound is None:
                unbound = True

            self.__cache[instance] = (
                self.__dependent_class(instance)
                if unbound
                else self.__dependent_class()
            )
        return self.__cache[instance]


class ClassProperty(classmethod):
    def __init__(self, f):
        super().__init__(f)
        self.fget = self.__func__
        self.fset = None

    def __get__(self, instance: Any, owner: type | None = None):
        if instance is None:
            cls = owner
        else:
            if isinstance(instance, type):
                cls = instance
            else:
                cls = type(instance)
        return self.fget(cls)

    def __set__(self, instance, value):
        if isinstance(instance, type):
            cls = instance
        else:
            cls = type(instance)
        self.fset(cls, value)

    def getter(self, func):
        self.fget = func
        return self

    def setter(self, func):
        self.fset = func
        return self


def class_property(property_fn):
    return ClassProperty(property_fn)
