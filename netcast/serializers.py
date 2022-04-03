from __future__ import annotations  # Python 3.8

import functools
from typing import Type, Any, Mapping, Callable
from types import MappingProxyType, SimpleNamespace as SimpleNamespaceType

from netcast.serializer import Serializer
from netcast.tools.normalization import numbered_object_name, object_array_name


__all__ = (
    "Bit",
    "Bool",
    "ModelSerializer",
    "Byte",
    "ByteArray",
    "Bytes",
    "Case",
    "Char",
    "Dict",
    "Double",
    "Float",
    "Float16",
    "Float32",
    "Float64",
    "FloatingPoint",
    "FrozenSet",
    "Half",
    "HalfByte",
    "Int",
    "Int128",
    "Int16",
    "Int256",
    "Int32",
    "Int512",
    "Int64",
    "Int8",
    "Integer",
    "List",
    "Long",
    "LongInt",
    "LongLong",
    "LongLongInt",
    "MappingProxy",
    "Nibble",
    "Number",
    "Range",
    "Serializer",
    "Set",
    "Short",
    "ShortInt",
    "Signed",
    "SignedByte",
    "SignedChar",
    "SignedInt",
    "SignedInteger",
    "SignedInt128",
    "SignedInt16",
    "SignedInt256",
    "SignedInt32",
    "SignedInt512",
    "SignedInt64",
    "SignedInt8",
    "SignedLong",
    "SignedLongInt",
    "SignedLongLong",
    "SignedLongLongInt",
    "SignedNumber",
    "Simple",
    "SimpleNamespace",
    "Single",
    "String",
    "Switch",
    "Tetrade",
    "Tuple",
    "Type",
    "Unsigned",
    "UnsignedByte",
    "UnsignedChar",
    "UnsignedInt",
    "UnsignedInt128",
    "UnsignedInt16",
    "UnsignedInt256",
    "UnsignedInt32",
    "UnsignedInt512",
    "UnsignedInt64",
    "UnsignedInt8",
    "UnsignedLong",
    "UnsignedLongInt",
    "UnsignedLongLong",
    "UnsignedLongLongInt",
)


class Object(Serializer):
    """Base class for all objects."""

    def __class_getitem__(cls, size):
        if size < 1:
            raise ValueError("dimension size must be at least 1")
        from netcast import create_model
        name = cls.__name__
        components = (cls(name=numbered_object_name(cls, name, i+1)) for i in range(size))
        name = object_array_name(cls, name, size)
        return create_model(*components, name=name)

    def __getitem__(self, size):
        if size < 1:
            raise ValueError("dimension size must be at least 1")
        from netcast import create_model

        cls = type(self)
        name = self.name
        if name:
            name = cls.__name__
        components = (self(name=numbered_object_name(cls, name, i+1)) for i in range(size))
        name = object_array_name(cls, name, size)
        return create_model(*components, name=name)


class Const(Object):
    """A constant object."""

    def __init__(self, obj: Any, **settings: Any):
        self.obj = obj
        super().__init__(**settings)


class Simple(Object):
    """Base class for all primitive types."""


class Number(Simple):
    """
    Base class for all numbers.

    This rather refers only to the "real" numbers,
    but "number" itself sounds better.
    """


class Integer(Number):
    """Base integer type."""

    load_type = int


class FloatingPoint(Number):
    """Base class for all floats."""

    load_type = float


class Range(Object):
    """Base class for range objects."""


class ModelSerializer(Object):
    """Base class for all types storing models states."""


class Dict(ModelSerializer):
    """Base class for all dictionaries."""

    load_type = dict


class MappingProxy(Dict):
    """Base class for all mapping proxies."""

    load_type = MappingProxyType


class SimpleNamespace(Dict):
    """Base class for all simple namespaces."""

    load_type = SimpleNamespaceType

    @functools.singledispatchmethod
    def load_type_factory(self, obj: Mapping):
        return SimpleNamespace.load_type(**obj)


class Sequence(ModelSerializer):
    """Base class for all sequences."""

    @functools.singledispatchmethod
    def load_type_factory(self, obj: Any):
        if callable(getattr(obj, "values", None)):
            return self.load_type(obj.values())
        return self.load_type(obj)


class List(Sequence):
    """Base class for all lists."""

    load_type = list


class Tuple(Sequence):
    """Base class for all tuples."""

    load_type = tuple


class Set(Sequence):
    """Base class for all sets."""

    load_type = set


class FrozenSet(Sequence):
    """Base class for all frozen sets."""

    load_type = frozenset


class String(Sequence):
    """Base class for all strings."""

    load_type = str

    @functools.singledispatchmethod
    def load_type_factory(self, obj: Any):
        if callable(getattr(obj, "values", None)):
            return self.load_type().join(obj.values())
        return self.load_type(obj)


class Bytes(String):
    """Base class for all byte strings."""

    load_type = bytes


class ByteArray(String):
    """Base class for all byte arrays."""

    load_type = bytearray


SignedNumber = Number
SignedInteger = Integer
Bool = Bit = Integer(bit_size=1, signed=False)
Nibble = HalfByte = Tetrade = Integer(bit_size=4, signed=False)

# A few aliases for the easier implementation of serializers in C-associated protocols.
# You must support `bit_size` and `signed` settings in your interface to make this work.
SignedInt8 = Int8 = Integer(bit_size=8, signed=True)
SignedInt16 = Int16 = Integer(bit_size=16, signed=True)
SignedInt24 = Int24 = Integer(bit_size=24, signed=True)
SignedInt32 = Int32 = Integer(bit_size=32, signed=True)
SignedInt64 = Int64 = Integer(bit_size=64, signed=True)
SignedInt128 = Int128 = Integer(bit_size=128, signed=True)
SignedInt256 = Int256 = Integer(bit_size=256, signed=True)
SignedInt512 = Int512 = Integer(bit_size=512, signed=True)

UnsignedInt8 = Integer(bit_size=8, signed=False)
UnsignedInt16 = Integer(bit_size=16, signed=False)
UnsignedInt24 = Integer(bit_size=24, signed=False)
UnsignedInt32 = Integer(bit_size=32, signed=False)
UnsignedInt64 = Integer(bit_size=64, signed=False)
UnsignedInt128 = Integer(bit_size=128, signed=False)
UnsignedInt256 = Integer(bit_size=256, signed=False)
UnsignedInt512 = Integer(bit_size=512, signed=False)

Byte = SignedByte = Char = SignedChar = SignedInt8
UnsignedByte = UnsignedChar = UnsignedInt8

Short = ShortInt = Int16
Int = Long = LongInt = Int32
Signed = SignedInt = SignedLong = SignedLongInt = Int32
Unsigned = UnsignedInt = UnsignedLong = UnsignedLongInt = UnsignedInt32
LongLong = LongLongInt = SignedLongLong = SignedLongLongInt = Int64
UnsignedLongLong = UnsignedLongLongInt = UnsignedInt64

Float16 = FloatingPoint(bit_size=16)
Float32 = FloatingPoint(bit_size=32)
Float64 = FloatingPoint(bit_size=64)

Half = Float16
Single = Float = Float32
Double = Float64


class Statement(Object):
    """Base class for all statements that indicate a dynamic behaviour."""


class Switch(Statement):
    """
    Switch statement.
    """
    def __init__(
            self, *,
            func: Callable,
            cases: Tuple[Case, ...] = (),
            **settings: Any
    ):
        self.func = func
        self.cases = cases
        super().__init__(**settings)


class Case(Statement):
    """Base class for all switch-statement cases."""

    def __init__(self, *, key: Any, obj: Any, **settings: Any):
        self.key = key
        if not isinstance(obj, Object):
            obj = Const(obj, **settings)
        self.obj = obj
        super().__init__(**settings)
