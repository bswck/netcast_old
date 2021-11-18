from typing import Type, TypeVar, Sequence

import construct as cs

C = TypeVar('C', bound=cs.Construct)
M = object()
_main_registry = {
    'construct': {},
    'factory': {},
    'aliased_args': {},
    'reserve_args': {}
}
IGNORE_ATTRS = (
    '__repr__',
    '__hash__',
    '__str__',
    '__getattribute__',
    '__setattr__',
    '__delattr__',
    '__lt__',
    '__le__',
    '__eq__',
    '__ne__',
    '__gt__',
    '__ge__',
    '__init__',
    '__new__',
    '__reduce_ex__',
    '__reduce__',
    '__subclasshook__',
    '__init_subclass__',
    '__format__',
    '__sizeof__',
    '__dir__',
    '__class__',
    '__doc__',
    '__module__'
)


def _create_registry_api(key, default=M, raise_missing=False, registry=None):
    if registry is None:
        registry = _main_registry

    def _get(obj, suppress_missing=False):
        raise_missing_here = raise_missing and not suppress_missing
        v = registry[key].get(id(obj), default)
        if v is default and raise_missing_here:
            raise ValueError(f'{key} is missing')
        return v

    def _set(obj, value):
        registry[key][id(obj)] = value

    return _get, _set


get_factory, set_factory = _create_registry_api('factory', raise_missing=True)
get_construct, set_construct = _create_registry_api('construct', raise_missing=True)
get_reserve_args, set_reserve_args = _create_registry_api('reserve_args', default={})
get_aliased_args, set_aliased_args = _create_registry_api('aliased_args', default={})


def get_public_vars(cls):
    d = cls if isinstance(cls, dict) else vars(cls)
    return {k: v for k, v in d.items() if not (k.startswith('__') and k.endswith('__'))}


def ensure_wrapped_field(value, name):
    if not isinstance(value, FieldDescriptor):
        value = FieldDescriptor(value, name)
    return value


def get_alias(name):
    return name + '_alias'


class UnboundFieldError(ValueError):
    pass


class FieldDescriptor(cs.Subconstruct):  # noqa
    def __init__(self, subcon, name, default=M):
        if not isinstance(subcon, cs.Construct):
            if isinstance(subcon, cs.bytestringtype):
                subcon = cs.Const(subcon)
            else:
                raise ValueError(
                    f'attempted to cast a non-construct field {name!r} to a constant field, '
                    'but it is not a byte string; consider using construct.Const '
                    'or construct.Default'
                )
        super().__init__(subcon)
        self.name = name
        self.default = default
        self._values = {}

    def __get__(self, instance, owner):
        value = self._values.get(id(instance), M)
        if value is M:
            if isinstance(self.subcon, cs.Const):
                return self.subcon.value
            if self.default is M:
                raise UnboundFieldError(self.name)
            return self.default
        return value

    def __set__(self, instance, value):
        self._values[id(instance)] = value

    def __truediv__(self, other):
        return cs.Renamed(self, other)

    __rtruediv__ = __truediv__


def finalize_args(cls, args=None):
    if args is None:
        args = vars(cls)
    reserve_args = get_reserve_args(cls)
    aliased_args = {}
    final_args = {}
    for name, attr in reserve_args.items():
        if name in args:
            aliased_arg = get_alias(name)
            if aliased_arg in args:
                raise ValueError(f'cannot alias argument {name}: {aliased_arg} taken')
            aliased_args[aliased_arg] = name
            final_args[name] = args.pop(attr)
        else:
            arg = args.get(attr, M)
            if arg is not M:
                final_args[name] = arg
    set_aliased_args(cls, aliased_args)
    for name, value in args.items():
        if name in IGNORE_ATTRS:
            continue
        set_name = name
        if name in aliased_args:
            set_name = get_alias(name)
        final_args[set_name] = field = ensure_wrapped_field(value, name)
        setattr(cls, name, field)
    return final_args


class ConstructAttributeTree:
    __setup__ = True

    def _serialize_from_object(self, obj, **context_kwds):
        return get_construct(type(self)).build(obj, **context_kwds)

    def _serialize(self, **obj):
        return self._serialize_from_object(obj)

    __call__ = _build = _serialize

    def _parse(self, byte_string, **context_kwds):
        return get_construct(type(self)).parse(byte_string, **context_kwds)

    _reinterpret = _parse

    def __new__(cls, **args):
        if get_construct(cls, suppress_missing=True) is M:
            return prepare_subclass(cls, args)
        elif args:
            if not get_public_vars(cls):
                return prepare_subclass(cls, args)
            raise TypeError(f'__new__() got an unexpected keyword argument {list(args)[0]!r}')
        return object.__new__(cls)


def init_subclass(cls):
    cls.__setup__ and set_construct(cls, get_factory(cls.mro()[1])(**finalize_args(cls)))


def prepare_subclass(cls, args):
    subcls = type(cls.__name__, (cls,), {'__setup__': False})
    set_factory(subcls, get_factory(cls))
    set_construct(subcls, get_factory(cls)(**finalize_args(cls, args=args)))
    return object.__new__(subcls)  # type: ignore


def port(
        factory: Type[C],
        reserve_args: Sequence[str] = (),
        **custom_reserve_args: str
):
    reserve_args = {name: f'__{name}__' for name in reserve_args}
    for name, reservation in custom_reserve_args.items():
        if name in reserve_args:
            raise ValueError(f'double-passed {name!r} in reserved args')
        reserve_args[name] = reservation
    cls = type(
        factory.__name__,
        (ConstructAttributeTree,),
        {'__init_subclass__': init_subclass}
    )
    set_factory(cls, factory)
    set_reserve_args(cls, reserve_args)
    return cls


Struct = port(cs.Struct)
Sequence = port(cs.Sequence)
FocusedSeq = port(cs.FocusedSeq, ['parsebuildfrom'])
Union = port(cs.Union, ['parsefrom'])
Select = port(cs.Select)
LazyStruct = port(cs.LazyStruct)
