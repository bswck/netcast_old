import abc

from netcast.cast.datatype import DataType


class Array(DataType, metaclass=abc.ABCMeta, family=True):
    """Base class for all array types."""

    inherit_context = False

    @property
    def type_key(self):
        return 'Array'

