from __future__ import annotations

import dataclasses
import functools
import inspect
import operator
from typing import Callable, ClassVar, TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from netcast.serializer import Serializer


class Plugin:
    """Plugin is a serializer mix-in."""

    __features__: ClassVar[dict[str, Callable]] = {}
    total_dependents = 0

    def __init__(self: Plugin | Serializer, **cfg):
        """Save your options here"""

    def __init_subclass__(cls, **kwargs):
        if cls not in Plugin.__subclasses__():
            return
        independent, dependent = {}, {}
        for attr, feature in inspect.getmembers(cls, predicate=cls.feature_predicate):
            if feature.is_dependent:
                dependent[attr] = feature
            else:
                independent[attr] = feature
            cls.total_dependents = len(dependent)
        cls.__features__.update(**independent, **dependent)

    @staticmethod
    def feature_predicate(obj):
        return isinstance(obj, _Feature) and not obj.disabled

    @classmethod
    def get_plugins(cls, serializer_class):
        return tuple(
            sorted(
                filter(
                    lambda base: base in cls.__subclasses__(),
                    serializer_class.__bases__,
                ),
                key=operator.attrgetter("total_dependents"),
            )
        )


@dataclasses.dataclass
class _Feature:
    # pylint: disable=R0902

    func: Optional[Callable] = dataclasses.field(default=None, repr=False)
    default: Any = dataclasses.field(default=None, repr=False)
    disabled: bool = False
    override: bool = False
    call_before: str | None = None
    call_after: str | None = None
    precedential_reshaping: bool = False
    hook_takes_method: bool = False
    finalizer_takes_result: bool = False
    is_dependent: bool = False

    def __post_init__(self):
        if self.func and self.default:
            raise ValueError("feature can't simultaneously hold a func and a value")

    @property
    def is_hook(self):
        return any((self.call_before, self.call_after))

    def __call__(self, params):
        return params.call(self.func)


def default(value=None):
    return _Feature(default=value)


def feature_or_hook(func=None, **kwargs) -> functools.partial[_Feature] | _Feature:
    if func is None:
        return functools.partial(export, **kwargs)
    return _Feature(func, **kwargs)


export = hook = feature_or_hook
