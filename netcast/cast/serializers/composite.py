import abc

from netcast.cast.serializer import Serializer
from netcast.toolkit.symbol import Symbol


class Composite(Serializer, abc.ABC):
    """Base class for all sequence types."""
    __load_type__ = Symbol('Composite')

    new_context = True


class List(Composite, abc.ABC):
    """Base class for all lists."""
    __load_type__ = list


class Dict(Composite, abc.ABC):
    """Base class for all dictionaries."""
    __load_type__ = dict


class Tuple(Composite, abc.ABC):
    """Base class for all tuples."""
    __load_type__ = tuple


class String(Composite, abc.ABC):
    """Base class for all strings."""
    __load_type__ = str


Str = String


class Bytes(Composite, abc.ABC):
    """Base class for all byte strings."""
    __load_type__ = bytes


class ByteArray(Composite, abc.ABC):
    """Base class for all byte arrays."""
    __load_type__ = bytearray
