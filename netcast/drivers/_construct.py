from __future__ import annotations

import construct
import netcast as nc

DRIVER_NAME = "construct"


class ConstructInterface(nc.DriverInterface):
    dump_type = bytes

    def __init__(
            self,
            name=None,
            *,
            compiled=False,
            coerce_after_loading=True,
            coerce_before_dumping=False,
            **settings
    ):
        super().__init__(name, **settings)
        self.compiled = compiled
        self.coerce_after_loading = coerce_after_loading
        self.coerce_before_dumping = coerce_before_dumping


class Number(nc.Number, ConstructInterface):
    def __init__(
            self,
            name=None,
            *,
            big_endian=None,
            little_endian=None,
            native_endian=None,
            cpu_sized=True,
            compiled=False,
            **settings
    ):
        ConstructInterface.__init__(self, name=name, compiled=compiled, **settings)

        if cpu_sized and any(map(callable, (big_endian, little_endian, native_endian))):
            cpu_sized = False

        self.little = little_endian
        self.big = big_endian
        self.native = native_endian
        self.cpu_sized = cpu_sized

        impl = None

        if cpu_sized:
            impl = self.get_format_field()
            self.cpu_sized = False

        if impl is None:
            impl = self.get_bytes_integer()

        if impl is None:
            raise NotImplementedError(f"construct does not support {self}")

        self._impl = impl

    def get_swapped(self):
        if self.big is None and self.native is None and self.little is not None:
            return self.little
        if self.big is None and self.native is not None:
            return self.native
        return True if self.big is None else self.big

    def get_bytes_integer(self):
        byte_length = self.bit_size >> 3
        return construct.BytesInteger(
            byte_length, signed=self.signed,
            swapped=self.get_swapped()
        )

    def get_format_field(self):
        type_name = "Int" if self.load_type is int else "Float"
        type_name += str(self.bit_size)
        type_name += ("s" if self.signed else "u") if self.load_type is int else ""
        if self.big:
            type_name += "b"
        elif self.little:
            type_name += "l"
        else:
            type_name += "n"
        obj = getattr(construct, type_name, None)
        return obj


class Sequence(nc.BulkSerializer, ConstructInterface):
    def __init__(
            self,
            name=None,
            *fields,
            compiled=False,
            **settings
    ):
        ConstructInterface.__init__(self, name=name, compiled=compiled, **settings)
        self._impl = construct.Sequence(*self.ensure_impls(fields, settings))


class Array(nc.BulkSerializer, ConstructInterface):
    def __init__(
            self,
            data_type,
            name=None,
            size=None,
            prefixed=False,
            lazy=False,
            compiled=False,
            **settings
    ):
        ConstructInterface.__init__(self, name=name, compiled=compiled, **settings)

        if prefixed and lazy:
            raise ValueError("array can't be prefixed and lazy at the same time")

        if size is None:
            size = driver.UnsignedInt8(compiled=compiled).impl

        self.data_type_impl = data_type_impl = self.ensure_impl(data_type, **settings)

        if prefixed:
            if isinstance(size, int) and 0 <= size < 256:
                size = construct.Const(bytes([size]))
            else:
                raise ValueError("expected a netcast data type!")

            self._impl = construct.PrefixedArray(size, data_type_impl)

        elif lazy:
            if not isinstance(size, int) or not callable(size):
                raise ValueError("expected an integer or a callable that returns integer")

            self._impl = construct.LazyArray(size, data_type_impl)

        else:
            self._impl = construct.Array(size, data_type_impl)


class Struct(nc.BulkSerializer, ConstructInterface):
    def __init__(
            self,
            *fields,
            name=None,
            alignment_modulus=None,
            compiled=False,
            **settings
    ):
        ConstructInterface.__init__(self, name=name, compiled=compiled, **settings)
        field_map = self.ensure_impls(fields, settings)
        if alignment_modulus is None:
            impl = construct.Struct(*field_map)
        else:
            impl = construct.AlignedStruct(alignment_modulus, *field_map)
        self._impl = impl


class ConstructDriver(nc.Driver):
    NumberImpl = nc.adapter(Number)
    SequenceImpl = nc.adapter(Sequence)
    ArrayImpl = nc.adapter(Array)
    StructImpl = nc.adapter(Struct)

    SignedInt8 = NumberImpl(nc.SignedInt8)
    SignedInt16 = NumberImpl(nc.SignedInt16)
    SignedInt32 = NumberImpl(nc.SignedInt32)
    SignedInt64 = NumberImpl(nc.SignedInt64)
    SignedInt128 = NumberImpl(nc.SignedInt128)
    SignedInt256 = NumberImpl(nc.SignedInt256)
    SignedInt512 = NumberImpl(nc.SignedInt512)
    UnsignedInt8 = NumberImpl(nc.UnsignedInt8)
    UnsignedInt16 = NumberImpl(nc.UnsignedInt16)
    UnsignedInt32 = NumberImpl(nc.UnsignedInt32)
    UnsignedInt64 = NumberImpl(nc.UnsignedInt64)
    UnsignedInt128 = NumberImpl(nc.UnsignedInt128)
    UnsignedInt256 = NumberImpl(nc.UnsignedInt256)
    Float16 = NumberImpl(nc.Float16)
    Float32 = NumberImpl(nc.Float32)
    Float64 = NumberImpl(nc.Float64)

    ListSequence = SequenceImpl(nc.List)
    TupleSequence = SequenceImpl(nc.Tuple)
    SetSequence = SequenceImpl(nc.Set)
    FrozenSetSequence = SequenceImpl(nc.FrozenSet)
    Sequence = ListSequence

    ListArray = ArrayImpl(nc.List)
    TupleArray = ArrayImpl(nc.Tuple)
    SetArray = ArrayImpl(nc.Set)
    FrozenSetArray = ArrayImpl(nc.FrozenSet)
    Array = ListArray

    DictStruct = StructImpl(nc.Dict)
    MappingProxyStruct = StructImpl(nc.MappingProxy)
    SimpleNamespaceStruct = StructImpl(nc.SimpleNamespace)
    Struct = DictStruct


driver = ConstructDriver
