from __future__ import annotations

import abc
import dataclasses
from typing import ClassVar, Any, Type

from netcast.context import Context, ConstructContext


class _HasContext:
    context: Context = dataclasses.field(default_factory=ConstructContext)


@dataclasses.dataclass
class Load(_HasContext):
    load: Any
    cast: Cast

    @abc.abstractmethod
    def dump(self, *args, **kwargs) -> Dump:
        pass

    __call__ = dump


@dataclasses.dataclass
class Dump(_HasContext):
    dump: Any
    cast: Cast

    @abc.abstractmethod
    def load(self, *args, **kwargs) -> Load:
        pass

    __call__ = load


class Cast(abc.ABC):
    """
    A singleton abstract class for cast rules.
    See also :package:`netcast.cast`.
    """

    load_type: ClassVar[type]
    dump_type: ClassVar[type]
    load_factory: ClassVar[Type[Load]]
    dump_factory: ClassVar[Type[Dump]]

    def dump(self, load: load_type | load_factory, *args, **kwargs) -> Dump:
        dump = self.load_factory(load)
        return dump(*args, **kwargs)

    def load(self, dump: dump_type | dump_factory, *args, **kwargs) -> Load:
        load = self.dump_factory(dump)
        return load(*args, **kwargs)
