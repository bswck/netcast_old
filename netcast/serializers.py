from __future__ import annotations

import functools
from typing import Type
from types import MappingProxyType, SimpleNamespace as SimpleNamespaceType

from netcast.serializer import Serializer


__all__ = (
    "float_type",
    "int_type",
    "FloatingPoint",
    "Integer",
    "AnySignedInt",
    "Bit",
    "Bool",
    "ModelSerializer",
    "Byte",
    "ByteArray",
    "Bytes",
    "Char",
    "Dict",
    "Double",
    "Float16",
    "Float32",
    "Float64",
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
    "List",
    "Long",
    "LongInt",
    "LongLong",
    "LongLongInt",
    "MappingProxy",
    "Nibble",
    "Number",
    "Serializer",
    "Set",
    "Short",
    "ShortInt",
    "Signed",
    "SignedByte",
    "SignedChar",
    "SignedInt",
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


class Simple(Serializer):
    """Base class for all primitive types."""


class Number(Simple):
    """
    Base class for all numbers.

    This rather refers only to the "real" numbers,
    but "number" itself sounds better.
    """

    bit_size = float("infinity")


class Integer(Number):
    """Base integer type."""

    load_type = int
    signed = True

    def __init__(self, *args, signed=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.signed = signed

        if signed is not None:
            if signed and not self.signed:
                raise ValueError("signed-unsigned configuration conflict")


class FloatingPoint(Number):
    """Base class for all floats."""

    load_type = float


class ModelSerializer(Serializer):
    """Base class for all types for storing bound models."""


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
    def load_type_factory(self, mapping):
        return self.load_type(**mapping)


class Sequence(ModelSerializer):
    """Base class for all sequences."""

    @functools.singledispatchmethod
    def load_type_factory(self, obj):
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
    def load_type_factory(self, obj):
        if callable(getattr(obj, "values", None)):
            return self.load_type().join(obj.values())
        return self.load_type(obj)


class Bytes(String):
    """Base class for all byte strings."""

    load_type = bytes


class ByteArray(String):
    """Base class for all byte arrays."""

    load_type = bytearray


def int_type(bit_size, signed=True) -> Type[Integer] | type:
    return type(
        "Int" + str(bit_size), (Integer,), {"bit_size": bit_size, "signed": signed}
    )


def float_type(bit_size):
    return type("Float" + str(bit_size), (FloatingPoint,), {"bit_size": bit_size})


SignedNumber = Number
AnySignedInt = Integer
Bool = Bit = int_type(1, signed=False)
Nibble = HalfByte = Tetrade = int_type(4, signed=False)

# A few aliases for the easier implementation of serializers in C-associated protocols.
SignedInt8 = Int8 = int_type(8)
SignedInt16 = Int16 = int_type(16)
SignedInt24 = Int24 = int_type(24)
SignedInt32 = Int32 = int_type(32)
SignedInt64 = Int64 = int_type(64)
SignedInt128 = Int128 = int_type(128)
SignedInt256 = Int256 = int_type(256)
SignedInt512 = Int512 = int_type(512)

UnsignedInt8 = int_type(8, signed=False)
UnsignedInt16 = int_type(16, signed=False)
UnsignedInt24 = int_type(24, signed=False)
UnsignedInt32 = int_type(32, signed=False)
UnsignedInt64 = int_type(64, signed=False)
UnsignedInt128 = int_type(128, signed=False)
UnsignedInt256 = int_type(256, signed=False)
UnsignedInt512 = int_type(512, signed=False)

Byte = SignedByte = Char = SignedChar = SignedInt8
UnsignedByte = UnsignedChar = UnsignedInt8

Short = ShortInt = Int16
Int = Long = LongInt = Int32
Signed = SignedInt = SignedLong = SignedLongInt = Int32
Unsigned = UnsignedInt = UnsignedLong = UnsignedLongInt = UnsignedInt32
LongLong = LongLongInt = SignedLongLong = SignedLongLongInt = Int64
UnsignedLongLong = UnsignedLongLongInt = UnsignedInt64

Float16 = float_type(16)
Float32 = float_type(32)
Float64 = float_type(64)

Half = Float16
Single = Float32
Double = Float64
