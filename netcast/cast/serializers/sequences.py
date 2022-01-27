import abc
import collections.abc

from netcast.cast.serializer import Serializer


class Sequence(Serializer, abc.ABC):
    """Base class for all sequence types."""
    __origin_type__ = collections.abc.Sequence
    new_context = True


class List(Sequence, abc.ABC):
    """Base class for all lists."""
    __origin_type__ = list


class Dict(Sequence, abc.ABC):
    """Base class for all dictionaries."""
    __origin_type__ = dict


class Tuple(Sequence, abc.ABC):
    """Base class for all tuples."""
    __origin_type__ = tuple


class String(Sequence, abc.ABC):
    """Base class for all strings."""
    __origin_type__ = str


class Bytes(Sequence, abc.ABC):
    """Base class for all byte strings."""
    __origin_type__ = bytes


class ByteArray(Sequence, abc.ABC):
    """Base class for all byte arrays."""
    __origin_type__ = bytearray
