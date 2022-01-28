from __future__ import annotations

import inspect
from typing import Callable, ClassVar, TYPE_CHECKING, Type

if TYPE_CHECKING:
    from netcast.cast.serializer import Serializer
    _PluginInnerT: Type[Plugin | Serializer]


class Plugin:
    """Plugin is a serializer mix-in. It might be used in """
    exported_features: ClassVar[dict[str, Callable]] = {}

    def __init__(self: _PluginInnerT, **cfg):
        """Save your options here"""

    def __init_subclass__(cls, **kwargs):
        members = inspect.getmembers(cls)


def get_plugins(cls):
    return tuple(filter(lambda base: isinstance(base, Plugin), cls.__bases__))
