from __future__ import annotations

from typing import Callable

from jaraco.collections import (
    KeyTransformingDict as _KeyTransformingDict,
    ItemsAsAttributes,
)

from netcast.constants import MISSING


class KeyTransformingDict(_KeyTransformingDict):
    # I don't know why update() doesn't call __setitem__(), either on CPython or PyPy
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

    _pointers = {}

    def restore_key(self, key):
        return self._pointers.pop(key)

    def transform_key(self, key):
        id_of_key = id(key)
        self._pointers[id_of_key] = key
        return id_of_key


class AttributeDict(dict, ItemsAsAttributes):
    """A modern dictionary with attribute-as-item access."""

    def __setattr__(self, key, value):
        """self[key] = value, but via attribute setting"""
        self.__setitem__(key, value)

    def __dir__(self):
        """List all accessible names bound to this object."""
        return list(self.keys())


class ParameterContainer:
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
    def from_call(cls, *arguments, **keywords):
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
        chunks = tuple(filter(None, (self.repr_arguments(), self.repr_keywords())))
        if not chunks:
            return "(no parameters)"
        return ", ".join(chunks).join("()")


parameters = ParameterContainer.from_call


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
