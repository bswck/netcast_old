import abc

from netcast.cast.datatype import DataType


class Sequence(DataType, abc.ABC):
    """Base class for all sequence types."""
    __type_key__ = 'sequence'
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
    __type_key__ = 'string'
    __origin_type__ = str


class Bytes(Sequence, abc.ABC):
    """Base class for all byte strings."""
    __type_key__ = 'bytestring'
    __origin_type__ = bytes


class ByteArray(Sequence, abc.ABC):
    """Base class for all byte strings."""
    __type_key__ = 'bytearray'
    __origin_type__ = bytearray
