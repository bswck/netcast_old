import abc

from netcast.serializer import Serializer


class Composite(Serializer, abc.ABC):
    """Base class for all sequence types."""
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
