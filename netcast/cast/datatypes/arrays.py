import abc

from netcast.cast.datatype import DataType


class Array(DataType, abc.ABC):
    """Base class for all array types."""
    __type_key__ = 'array'
    new_context = True


class List(Array, abc.ABC):
    """Base class for all list types."""
    __origin_type__ = list


class Dict(Array, abc.ABC):
    __origin_type__ = dict


print(Dict.get_context())