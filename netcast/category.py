from __future__ import annotations  # Python 3.8

import functools  # noqa: F401
import itertools  # noqa: F401
import sys  # noqa: F401
import typing

from netcast.tools.arrangements import ClassArrangement

if typing.TYPE_CHECKING:
    from netcast.driver import Driver  # noqa: F401


__all__ = (
    "Category",
    "get_global_category",
    "get_category"
)


class Category(ClassArrangement):
    separator = "::"
    categories = {}

    def __init__(self):
        self.drivers = {}
    #
    # def __call__(self, category: str):
    #     key, _, next_keys = category.partition(self.separator)
    #     try:
    #         categories = self.categories[key]
    #     except KeyError as err:
    #         raise NotImplementedError(f"no drivers found in category {key}") from err
    #     try:
    #         self.categories[key]
    #     except KeyError as err:
    #         raise NotImplementedError(f"no drivers found in category {key}") from err
    #     return engine
    #
    # def get_driver(self, name: str = "default") -> Driver:
    #     name = sys.intern(name)
    #     return self.drivers.get(name)
    #
    # def register(self, driver=None, *, category="netcast", default=False):
    #     if driver is None:
    #         return functools.partial(self.register, category=category, default=default)
    #     keys = category.split(self.separator)
    #     return driver


__global_engine = None


def get_global_category():
    global __global_engine
    if __global_engine is None:
        __global_engine = Category()
    return __global_engine


def get_category():
    category = get_global_category()
    return category
