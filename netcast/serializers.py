from __future__ import annotations

import abc
import math
from typing import Type

from netcast.serializer import Serializer


__all__ = (
    "Bit",
    "Bool",
    "Byte",
    "Char",
    "Double",
    "Float16",
    "Float32",
    "Float64",
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
    "Long",
    "LongInt",
    "LongLong",
    "LongLongInt",
    "Nibble",
    "Primitive",
    "Real",
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
    "SignedReal",
    "Single",
    "Tetrade",
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
    "UnsignedReal",
    "int_type",
)


class Primitive(Serializer):
    """Base class for all primitive types."""


class Real(Primitive):
    bit_size = math.inf
    signed = True


class UnsignedReal(Real):
    signed = False


class AnyInt(Real):
    """Base integer type."""
    load_type = int


class AnyUnsignedInt(UnsignedReal):
    """Base unsigned integer type."""
    load_type = int


class AnyFloat(Real):
    """Base class for all floats."""
    load_type = float


class BulkSerializer(Serializer):
    """Base class for all composite types."""


class List(BulkSerializer):
    """Base class for all lists."""
    load_type = list


class Dict(BulkSerializer):
    """Base class for all dictionaries."""
    load_type = dict


class Tuple(BulkSerializer):
    """Base class for all tuples."""
    load_type = tuple


class String(BulkSerializer):
    """Base class for all strings."""
    load_type = str


class Bytes(BulkSerializer):
    """Base class for all byte strings."""
    load_type = bytes


class ByteArray(BulkSerializer):
    """Base class for all byte arrays."""
    load_type = bytearray


def int_type(bit_size, signed=True) -> Type[AnyInt] | type:
    name = ("Unsigned", "Signed")[signed] + "Int" + str(bit_size)
    return type(name, ((AnyUnsignedInt, AnySignedInt)[signed]), {"bit_size": bit_size})


def float_type(bit_size):
    name = "Float" + str(bit_size)
    return type(name, (AnyFloat,), {"bit_size": bit_size})


SignedReal = Real
AnySignedInt = AnyInt

Bool = Bit = int_type(1, signed=False)
Nibble = HalfByte = Tetrade = int_type(4, signed=False)

SignedInt8 = Int8 = int_type(8)
SignedInt16 = Int16 = int_type(16)
SignedInt32 = Int32 = int_type(32)
SignedInt64 = Int64 = int_type(64)
SignedInt128 = Int128 = int_type(128)
SignedInt256 = Int256 = int_type(256)
SignedInt512 = Int512 = int_type(512)

UnsignedInt8 = int_type(8, signed=False)
UnsignedInt16 = int_type(16, signed=False)
UnsignedInt32 = int_type(32, signed=False)
UnsignedInt64 = int_type(64, signed=False)
UnsignedInt128 = int_type(128, signed=False)
UnsignedInt256 = int_type(256, signed=False)
UnsignedInt512 = int_type(512, signed=False)

# A few aliases for the easier implementation of serializers in C-associated protocols.
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

# Aliases
Half = Float16
Single = Float32
Double = Float64
