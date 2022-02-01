from __future__ import annotations

import dataclasses
import functools
import inspect
import operator
from typing import Callable, ClassVar, TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from netcast.cast.serializer import Serializer


class Plugin:
    """Plugin is a serializer mix-in."""
    __features__: ClassVar[dict[str, Callable]] = {}
    dependents_count = 0

    def __init__(self: Plugin | Serializer, **cfg):
        """Save your options here"""

    def __init_subclass__(cls, **kwargs):
        independents, dependents = {}, {}
        for attr, feature_obj in inspect.getmembers(cls, predicate=feature_check):
            if feature_obj.dependent:
                dependents[attr] = feature_obj
            else:
                independents[attr] = feature_obj
            cls.dependents_count = len(dependents)
        cls.__features__.update(**independents, **dependents)


def feature_check(obj):
    return isinstance(obj, _Feature) and not obj.disabled


def get_plugins(cls):
    return tuple(sorted(
        filter(lambda base: base in Plugin.__subclasses__(), cls.__bases__),
        key=operator.attrgetter('dependents_count')
    ))


@dataclasses.dataclass
class _Feature:
    func: Optional[Callable] = dataclasses.field(default=None, repr=False)
    default: Any = dataclasses.field(default=None, repr=False)
    disabled: bool = False
    override: bool = False
    before: str | None = None
    after: str | None = None
    pass_method: bool = False
    finalizer_takes_result: bool = False
    dependent: bool = False

    def __post_init__(self):
        if self.func and self.default:
            raise ValueError('feature can\'t simultaneously hold a func and a value')

    @property
    def is_hook(self):
        return any((self.before, self.after))

    def __call__(self, *args, **kwargs):
        return self.func(*args, **kwargs)


def default(value=None):
    return _Feature(default=value)


def _decorator(func=None, **kwargs) -> functools.partial[_Feature] | _Feature:
    if func is None:
        return functools.partial(feature, **kwargs)
    return _Feature(func, **kwargs)


feature = hook = _decorator
