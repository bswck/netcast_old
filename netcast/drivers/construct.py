from __future__ import annotations

import construct
import netcast as nc


class Interface(nc.DriverInterface):
    dump_type = bytes

    def __init__(self, name=None, coercion_flags=0, compiled=True, **settings):
        super().__init__(name=name, coercion_flags=coercion_flags, **settings)
        self.compiled = compiled

    @property
    def impl(self):
        impl = self._impl
        if self.compiled:
            impl = impl.compile()
        if self.name is not None:
            impl = construct.Renamed(impl, self.name)
        return impl

    @property
    def driver(self):
        return driver


class Number(nc.Number, Interface):
    def __init__(
        self,
        name=None,
        *,
        big_endian=None,
        little_endian=None,
        native_endian=None,
        cpu_sized=True,
        compiled=False,
        signed=True,
        **settings,
    ):
        Interface.__init__(self, name=name, compiled=compiled, **settings)
        self.signed = signed

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
            byte_length, signed=self.signed, swapped=self.get_swapped()
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


class Sequence(nc.ModelSerializer, Interface):
    def __init__(self, name=None, *fields, compiled=False, **settings):
        Interface.__init__(self, name=name, compiled=compiled, **settings)
        self._impl = construct.Sequence(*self.get_impls(fields, settings))


class Array(nc.ModelSerializer, Interface):
    def __init__(
        self,
        data_type,
        name=None,
        size=None,
        prefixed=False,
        lazy=False,
        compiled=False,
        **settings,
    ):
        Interface.__init__(self, name=name, compiled=compiled, **settings)

        if prefixed and lazy:
            raise ValueError("array can't be prefixed and lazy at the same time")

        if size is None:
            size = driver.UnsignedInt8(compiled=compiled).impl

        self.data_type_impl = data_type_impl = self.get_impl(data_type, **settings)

        if prefixed:
            if isinstance(size, int) and 0 <= size < 256:
                size = construct.Const(bytes([size]))
            else:
                raise ValueError("expected a netcast data type!")

            self._impl = construct.PrefixedArray(size, data_type_impl)

        elif lazy:
            if not isinstance(size, int) or not callable(size):
                raise ValueError(
                    "expected an integer or a callable that returns integer"
                )

            self._impl = construct.LazyArray(size, data_type_impl)

        else:
            self._impl = construct.Array(size, data_type_impl)


class Struct(nc.ModelSerializer, Interface):
    def __init__(
        self, *fields, name=None, alignment_modulus=None, compiled=False, **settings
    ):
        Interface.__init__(self, name=name, compiled=compiled, **settings)
        impls = self.get_impls(fields, settings)
        if alignment_modulus is None:
            impl = construct.Struct(*impls)
        else:
            impl = construct.AlignedStruct(alignment_modulus, *impls)
        self._impl = impl


class ConstructDriver(nc.Driver):
    NumberMixin = nc.mixin(Number)
    SequenceMixin = nc.mixin(Sequence)
    ArrayMixin = nc.mixin(Array)
    StructMixin = nc.mixin(Struct)

    SignedInt8 = NumberMixin(nc.SignedInt8)
    SignedInt16 = NumberMixin(nc.SignedInt16)
    SignedInt32 = NumberMixin(nc.SignedInt32)
    SignedInt64 = NumberMixin(nc.SignedInt64)
    SignedInt128 = NumberMixin(nc.SignedInt128)
    SignedInt256 = NumberMixin(nc.SignedInt256)
    SignedInt512 = NumberMixin(nc.SignedInt512)
    UnsignedInt8 = NumberMixin(nc.UnsignedInt8)
    UnsignedInt16 = NumberMixin(nc.UnsignedInt16)
    UnsignedInt32 = NumberMixin(nc.UnsignedInt32)
    UnsignedInt64 = NumberMixin(nc.UnsignedInt64)
    UnsignedInt128 = NumberMixin(nc.UnsignedInt128)
    UnsignedInt256 = NumberMixin(nc.UnsignedInt256)
    Float16 = NumberMixin(nc.Float16)
    Float32 = NumberMixin(nc.Float32)
    Float64 = NumberMixin(nc.Float64)

    ListSequence = SequenceMixin(nc.List)
    TupleSequence = SequenceMixin(nc.Tuple)
    SetSequence = SequenceMixin(nc.Set)
    FrozenSetSequence = SequenceMixin(nc.FrozenSet)
    Sequence = ListSequence

    ListArray = ArrayMixin(nc.List)
    TupleArray = ArrayMixin(nc.Tuple)
    SetArray = ArrayMixin(nc.Set)
    FrozenSetArray = ArrayMixin(nc.FrozenSet)
    Array = ListArray

    DictStruct = StructMixin(nc.Dict)
    MappingProxyStruct = StructMixin(nc.MappingProxy)
    SimpleNamespaceStruct = StructMixin(nc.SimpleNamespace)
    Struct = DictStruct

    default_model_serializer = Struct


driver = ConstructDriver


@driver.get_model_serializer.register(Array)
def get_array_serializer(_, serializer, components=(), settings=None):
    if settings is None:
        settings = {}
    if len(components) != 1:
        raise ValueError("Array() takes exactly 1 argument")
    return serializer(*components, **settings)
