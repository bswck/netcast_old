from __future__ import annotations  # Python 3.8

import construct
import netcast as nc
from netcast import MISSING


DRIVER_NAME = "construct"


class Interface(nc.Interface):
    def __init__(self, **settings):
        self.compiled = settings.setdefault("compiled", not self.driver.DEBUG)
        self.wrap = True
        super().__init__(**settings)

    def impl(self, driver=None, settings=None, final=False):
        impl = self._impl

        if impl is NotImplemented:
            raise NotImplementedError("missing requested serializer implementation")

        if self.wrap:
            return self._wrap_impl(impl)
        return impl

    def _wrap_impl(self, impl):
        api_default = self.settings.get("api_default", MISSING)
        if api_default is not MISSING:
            impl = construct.Default(impl, api_default)

        one_of = self.settings.get("one_of")
        if one_of is not None:
            impl = construct.OneOf(impl, one_of)

        none_of = self.settings.get("none_of")
        if none_of is not None:
            impl = construct.NoneOf(impl, none_of)

        if_ = self.settings.get("if_", MISSING)
        else_ = self.settings.get("else_", MISSING)
        if if_ is not MISSING and else_ is MISSING:
            impl = construct.If(if_, impl)
        elif if_ is not MISSING and else_ is not MISSING:
            impl = construct.IfThenElse(if_, impl, else_)

        const = self.settings.get("const")
        if const is not None:
            impl = construct.Const(const, impl)

        padded = self.settings.get("padded")
        if padded:
            impl = construct.Padded(padded, impl)

        aligned = self.settings.get("aligned")
        if aligned is not None:
            impl = construct.Aligned(aligned, impl)

        null_terminated = self.settings.get("null_terminated", False)
        if null_terminated and not isinstance(impl, construct.StringEncoded):
            impl = construct.NullTerminated(impl)

        null_stripped = self.settings.get("null_stripped", False)
        if null_stripped:
            impl = construct.NullStripped(impl)

        optional = self.settings.get("optional", False)
        if optional:
            impl = construct.Optional(impl)

        if self.compiled:
            impl = impl.compile()

        if self.name is not None and (getattr(impl, "name", None) != self.name):
            impl = construct.Renamed(impl, self.name)

        return impl

    @property
    def driver(self):
        return Construct

    def _load(self, obj, settings, **kwargs):
        impl = self.impl()
        return impl.parse(obj)

    def _dump(self, obj, settings, **kwargs):
        impl = self.impl()
        return impl.build(obj)


class Sequence(Interface):
    implements = nc.ModelSerializer

    def __init__(self, *fields, **settings):
        super().__init__(**settings)
        self._impl = construct.Sequence(*self.get_impls(fields, self.settings))


class Array(Interface):
    implements = nc.ModelSerializer

    def __init__(self, data_type, /, **settings):
        size = settings.get("size")
        if size is None:
            size = Construct.UnsignedInt8(compiled=self.compiled).impl
        self.size = settings.setdefault("size", size)
        self.prefixed = settings.setdefault("prefixed", False)
        self.lazy = settings.setdefault("lazy", False)
        self.compiled = settings.setdefault("compiled", False)
        self.data_type = data_type
        super().__init__(**settings)

    def _configure(self, prefixed, lazy):
        self.data_type_impl = self.get_impl(self.data_type, **self.settings)

        size = self.size

        if prefixed and lazy:
            raise ValueError(
                "a binary array can't be prefixed and lazy at the same time"
            )

        if prefixed:
            if isinstance(size, int) and 0 <= size < 256:
                size = construct.Const(bytes([size]))
            else:
                raise ValueError("expected a netcast data type!")
            self._impl = construct.PrefixedArray(size, self.data_type_impl)
        elif lazy:
            if not isinstance(size, int) or not callable(size):
                raise ValueError(
                    "expected an integer or a callable that returns integer"
                )
            self._impl = construct.LazyArray(size, self.data_type_impl)
        else:
            self._impl = construct.Array(size, self.data_type_impl)


class Struct(Interface):
    implements = nc.ModelSerializer

    def __init__(self, *fields, **settings):
        self.fields = fields
        super().__init__(**settings)

    def _configure(self):
        self.impls = impls = self.get_impls(self.fields, self.settings)
        self._impl = construct.Struct(*impls)


class Construct(nc.Driver):
    SequenceInterface = nc.driver_interface(Sequence)
    ArrayInterface = nc.driver_interface(Array)
    StructInterface = nc.driver_interface(Struct)

    ListSequence = SequenceInterface(nc.List)
    TupleSequence = SequenceInterface(nc.Tuple)
    SetSequence = SequenceInterface(nc.Set)
    FrozenSetSequence = SequenceInterface(nc.FrozenSet)
    Sequence = ListSequence

    ListArray = ArrayInterface(nc.List)
    TupleArray = ArrayInterface(nc.Tuple)
    SetArray = ArrayInterface(nc.Set)
    FrozenSetArray = ArrayInterface(nc.FrozenSet)
    Array = ListArray

    DictStruct = StructInterface(nc.Dict)
    MappingProxyStruct = StructInterface(nc.MappingProxy)
    SimpleNamespaceStruct = StructInterface(nc.SimpleNamespace)
    Struct = DictStruct

    default_model_serializer = Struct


@Construct.impl
class Integer(Interface):
    implements = nc.Integer
    bit_size: int
    signed: bool

    def __init__(self, **settings):
        self.signed = settings.setdefault("signed", True)
        self.cpu_sized = settings.setdefault("cpu_sized", True)
        self.little_endian = settings.setdefault("little_endian", True)
        self.big_endian = settings.setdefault("big_endian", False)
        self.native_endian = settings.setdefault("native_endian", False)
        self.bit_size = settings.get("bit_size", 32)
        super().__init__(**settings)

    def _configure(
        self,
        *,
        signed,
        cpu_sized,
        big_endian,
        little_endian,
        native_endian,
    ):
        if cpu_sized and any(map(callable, (big_endian, little_endian, native_endian))):
            cpu_sized = False

        impl = None

        self.signed = signed

        if self.bit_size:
            if cpu_sized:
                impl = self.get_format_field()
                cpu_sized = False
            if impl is None:
                impl = self.get_bytes_integer()

        if impl is None:
            raise NotImplementedError(
                f"construct does not support {type(self).__name__}"
            )

        self.settings.update(signed=signed, cpu_sized=cpu_sized)
        self.cpu_sized = cpu_sized
        self._impl = impl

    def get_swapped(self):
        if (
            self.big_endian is None
            and self.native_endian is None
            and self.little_endian is not None
        ):
            return self.little_endian
        if self.big_endian is None and self.native_endian is not None:
            return self.native_endian
        return True if self.big_endian is None else self.big_endian

    def get_bytes_integer(self):
        byte_length = self.bit_size >> 3
        return construct.BytesInteger(
            byte_length, signed=self.signed, swapped=self.get_swapped()
        )

    def get_format_field(self):
        type_name = "Int" + str(self.bit_size) + "us"[self.signed]
        if self.big_endian:
            type_name += "b"
        elif self.little_endian:
            type_name += "l"
        else:
            type_name += "n"
        obj = getattr(construct, type_name, None)
        return obj


class _EncodingHack:
    def __init__(self):
        self._unit_cache = construct.possiblestringencodings.copy()

    def encoding_unit(self, encoding):
        """Create the encoding unit for a given encoding."""
        unit = self._unit_cache.get(encoding)
        if unit is None:
            unit = len("\x00".encode(encoding))
            self._unit_cache[encoding] = unit
        return bytes(unit)

    def c_string(self, encoding):
        encoding = encoding.casefold()
        macro = construct.StringEncoded(
            construct.NullTerminated(
                construct.GreedyBytes, term=self.encoding_unit(encoding)
            ),
            encoding,
        )

        def _netcast_emitfulltype(_ksy, _bitwise):
            return dict(type="strz", encoding=encoding)

        macro._emitfulltype = _netcast_emitfulltype
        return macro

    def padded_string(self, length, encoding):
        encoding = encoding.casefold()
        macro = construct.StringEncoded(
            construct.FixedSized(
                length,
                construct.NullStripped(
                    construct.GreedyBytes, pad=self.encoding_unit(encoding)
                ),
            ),
            encoding,
        )

        def _netcast_emitfulltype(_ksy, _bitwise):
            return dict(size=length, type="strz", encoding=encoding)

        macro._emitfulltype = _netcast_emitfulltype
        return macro


@Construct.impl
class String(Interface):
    implements = nc.String
    default_encoding = "ASCII"
    encoding_hack = _EncodingHack()

    def __init__(self, **settings):
        self.null_terminated = settings.setdefault("null_terminated", True)
        self.encoding = settings.setdefault("encoding", self.default_encoding)
        self.pascal = settings.setdefault("pascal", False)
        self.greedy = settings.setdefault("greedy", False)
        self.padded = settings.setdefault("padded", 0)
        self.size = settings.setdefault("size")
        super().__init__(**settings)

    def _configure(self, size, null_terminated, pascal, greedy, padded, encoding):
        impl = None
        if pascal or null_terminated:
            if null_terminated:
                impl = self.encoding_hack.c_string(encoding)
            elif padded:
                if size is None:
                    raise ValueError(
                        "undefined size for a fixed-size string serializer"
                    )
                impl = self.encoding_hack.padded_string(size, encoding)
            elif pascal:
                if size is None:
                    size = self.get_impl(self.driver.Int8(signed=False))
                impl = construct.PascalString(size, encoding)
            elif greedy:
                impl = construct.GreedyString(encoding)
        if impl is None:
            raise ValueError("invalid string serializer configuration")
        self._impl = impl


@Construct.impl
class FloatingPoint(Interface):
    implements = nc.FloatingPoint

    def __init__(self, **settings):
        self.bit_size = settings.get("bit_size", 32)  # float, double is 64
        super().__init__(**settings)

    def _configure(
        self,
        *,
        big_endian,
        little_endian,
        native_endian,
    ):
        impl = None
        if self.bit_size:
            impl = self.get_format_field()
        if impl is None:
            raise NotImplementedError(
                f"construct does not support {type(self).__name__}"
            )
        self._impl = impl

    def get_format_field(self):
        type_name = "Float" + str(self.bit_size)
        if self.big_endian:
            type_name += "b"
        elif self.little_endian:
            type_name += "l"
        else:
            type_name += "n"
        obj = getattr(construct, type_name, None)
        return obj


@Construct.impl
class Range(Interface):
    implements = nc.Range

    def __init__(self, obj, **settings):
        self.obj = obj
        super().__init__(**settings)

    def _configure(self):
        self._impl = construct.GreedyRange(self.get_impl(self.obj, **self.settings))


@Construct.impl
class Switch(Interface):
    implements = nc.Switch

    def __init__(self, *, func, cases=(), **settings):
        self.func = func
        self.cases = cases
        self.default_case = settings.setdefault("default_case")
        super().__init__(**settings)

    def _configure(self, default_case):
        cases = {
            case.key: self.get_impl(case.obj, **self.settings)
            for case in self.cases
        }
        self._impl = construct.Switch(self.func, cases, default_case)


@Construct.impl
class Case(Interface):
    implements = nc.Case

    def __init__(self, *, key, obj, **settings):
        self.key = key
        self.obj = obj
        self.wrap_impl = False
        super().__init__(**settings)

    def _configure(self, **settings):
        self._impl = self.get_impl(self.obj, **settings)


@Construct.get_model_serializer.register(Array)
def get_array_serializer(_, serializer, components=(), settings=None):
    if settings is None:
        settings = {}
    if len(components) != 1:
        raise ValueError("construct.Array() takes exactly 1 argument")
    return serializer(*components, **settings)
