from __future__ import annotations

import abc
import dataclasses
from typing import ClassVar, Any, Type

from netcast.context import DictContext


class ContextDataclass(DictContext):
    context: DictContext = dataclasses.field(default_factory=DictContext)


@dataclasses.dataclass
class Load(ContextDataclass):
    load: Any
    cast: Cast

    @abc.abstractmethod
    def dump(self, *args, **kwargs) -> Dump:
        pass

    __call__ = dump


@dataclasses.dataclass
class Dump(ContextDataclass):
    dump: Any
    cast: Cast

    @abc.abstractmethod
    def load(self) -> Load:
        pass

    __call__ = load


class Cast(abc.ABC):
    """
    A singleton abstract class for cast rules.
    See also :package:`netcast.cast`.
    """

    load_factory: ClassVar[Type[Load]]
    dump_factory: ClassVar[Type[Dump]]

    def dump(self, load: load_factory, *args, **kwargs) -> dump_factory:
        dump = self.load_factory(load)
        return dump(*args, **kwargs)

    def load(self, dump: dump_factory, *args, **kwargs) -> load_factory:
        load = self.dump_factory(dump)
        return load(*args, **kwargs)
