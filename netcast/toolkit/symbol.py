import dataclasses
import sys


@dataclasses.dataclass(frozen=True)
class Symbol:
    """An initializer-dependent singleton. Used as a mark or a sentinel."""

    __cache = {}
    __name_default = '_'

    name: str = dataclasses.field(default=__name_default)

    def __post_init__(self):
        self.__cache[self.name] = self

    def __new__(cls, name=__name_default):
        name = sys.intern(name)
        if name in cls.__cache:
            return cls.__cache[name]
        return object.__new__(cls)

    def __repr__(self):
        return self.name
