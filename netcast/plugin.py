from __future__ import annotations

import dataclasses
import functools
import inspect
import operator
from typing import Callable, ClassVar, TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from netcast.serializer import Serializer


def export_predicate(obj):
    return isinstance(obj, Export) and not obj.disabled


class Plugin:
    """Plugin is a serializer mix-in."""

    exports: ClassVar[dict[str, Callable]] = {}
    dependency_count: ClassVar[int] = 0

    def __init__(self: Plugin | Serializer, **cfg):
        """Save your options here"""
        self.cfg = cfg

    def __init_subclass__(cls, **kwargs):
        if cls not in Plugin.__subclasses__():
            return
        i, d = {}, {}
        for attr, feature in inspect.getmembers(cls, predicate=export_predicate):
            if feature.is_dependent:
                d[attr] = feature
            else:
                i[attr] = feature
            cls.dependency_count = len(d)
        cls.exports.update(**i, **d)

    @classmethod
    def get_plugins(cls, serializer_class):
        def predicate(super_class):
            return super_class in cls.__subclasses__()

        plugins = filter(predicate, serializer_class.__bases__)
        return sorted(plugins, key=operator.attrgetter("dependency_count"))


@dataclasses.dataclass
class Export:
    # pylint: disable=R0902

    func: Optional[Callable] = dataclasses.field(default=None, repr=False)
    default: Any = dataclasses.field(default=None, repr=False)
    disabled: bool = False
    override: bool = False
    call_before: str | None = None
    call_after: str | None = None
    initial_shaping: bool = False
    inform_with_method: bool = False
    communicate: bool = False
    is_dependent: bool = False

    __call__ = staticmethod(func)

    def __post_init__(self):
        if self.func and self.default:
            raise ValueError("feature can't simultaneously hold a func and a value")

    @property
    def is_hook(self):
        return any((self.call_before, self.call_after))


def default(value=None):
    return Export(default=value)


def export(func=None, **kwargs) -> functools.partial[Export] | Export:
    if func is None:
        return functools.partial(export, **kwargs)
    return Export(func, **kwargs)
