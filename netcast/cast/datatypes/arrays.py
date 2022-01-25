import abc

from netcast.cast.datatype import DataType


class Array(DataType, metaclass=abc.ABCMeta):
    """Base class for all array types."""

    __type_key__ = 'arrays'
    new_context = True


print(DataType.get_context())
print(Array.get_context())
