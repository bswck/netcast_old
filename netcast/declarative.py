import inspect
import types
from typing import Type, TypeVar, Sequence, Any

import construct as cs

IGNORE_ATTRS = (
    '__setup__', '__validate__',

    '__dict__', '__weakref__', '__repr__', '__hash__', '__str__', '__getattribute__',
    '__setattr__', '__delattr__', '__lt__', '__le__', '__eq__', '__ne__', '__gt__',
    '__ge__', '__init__', '__new__', '__reduce_ex__', '__reduce__',
    '__subclasshook__', '__init_subclass__', '__format__', '__sizeof__',
    '__dir__', '__class__', '__doc__', '__module__'
)

C = TypeVar('C', bound=cs.Construct)


class _Missing:
    def __repr__(self):
        return 'Missing'


M = _Missing()


_main_registry = {
    'constructs': {},
    'factories': {},
    'aliased_args': {},
    'reserve_args': {},
    'field_reg': {}
}


def _create_registry_api(
        key,
        default: Any = M,
        create_if_missing=True,
        raise_for_missing=False,
        registry=None
):
    if registry is None:
        registry = _main_registry

    def _get(obj, quiet_if_missing=False):
        raise_missing_here = raise_for_missing and not quiet_if_missing
        v = registry[key].get(id(obj), default)
        if create_if_missing and v is default:
            registry[key][id(obj)] = v
        if v is default and raise_missing_here:
            raise ValueError(f'value from {key} registry is missing')
        return v

    def _set(obj, value):
        registry[key][id(obj)] = value

    return _get, _set


get_factory, set_factory = _create_registry_api('factories', raise_for_missing=True)
get_construct, set_construct = _create_registry_api('constructs', raise_for_missing=True)
get_reserve_args, set_reserve_args = _create_registry_api('reserve_args', default={})
get_aliased_args, set_aliased_args = _create_registry_api('aliased_args', default={})
get_field_reg, set_field_reg = _create_registry_api('field_reg', default={})


def _ensure_type(obj):
    if isinstance(obj, type):
        return obj
    return type(obj)


def _finalize_args(cls, args=None):
    if args is None:
        args = get_fields(cls)
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
        final_args[set_name] = field = wrap_field(value, name)
        setattr(cls, name, field)
        field_reg = get_field_reg(cls)
        field_reg[name] = field
        set_field_reg(cls, field_reg)
    return final_args


def _subclass_hook(cls):
    cls.__setup__ and set_construct(cls, get_factory(cls.mro()[1])(**_finalize_args(cls)))


def _spawn_subclass(cls, args):
    subcls = type(cls.__name__, (cls,), {'__setup__': False})
    set_factory(subcls, get_factory(cls))
    set_construct(subcls, get_factory(cls)(**_finalize_args(cls, args=args)))
    return object.__new__(subcls)  # type: ignore


def serialize_from_object(decl, obj, **context_kwds):
    obj = {
        k: v for k, v in {**get_fields(decl, final=True), **obj}.items()
        if v is not M
    }
    return get_construct(_ensure_type(decl)).build(obj, **context_kwds)


def serialize(decl, **obj):
    return serialize_from_object(decl, obj)


def reinterpret(decl, byte_string, **context_kwds):
    container = get_construct(_ensure_type(decl)).parse(byte_string, **context_kwds)
    for key, val in container.items():
        setattr(decl, key, val)
    return decl


def create_decl(
        factory: Type[C],
        reserve_args: Sequence[str] = (),
        **custom_reserve_args: str
):
    reserve_args = {name: f'__{name}__' for name in reserve_args}
    for name, reserved_arg in custom_reserve_args.items():
        if name in reserve_args:
            raise ValueError(f'double-passed {name!r} in reserved args')
        reserve_args[name] = reserved_arg
    cls = type(
        factory.__name__,
        (DeclarativeConstruct,),
        {'__init_subclass__': _subclass_hook}
    )
    set_factory(cls, factory)
    set_reserve_args(cls, reserve_args)
    return cls


def get_fields(cls, aliased_form=False, final=False):
    if final:
        aliased_form = True
    field_reg = get_field_reg(cls)
    if field_reg:
        d = dict(field_reg)
    else:
        d = cls if isinstance(cls, dict) else {k: getattr(cls, k) for k in dir(cls)}
    return {
        (
            get_alias(k)
            if k in get_aliased_args(cls)
            and aliased_form
            else k
        ): v.get(cls) if final else v
        for k, v in d.items()
        if k not in IGNORE_ATTRS
    }


def wrap_field(value, name):
    if not isinstance(value, FieldDescriptor):
        value = FieldDescriptor(value, name)
    return value


def get_alias(name):
    return name + '_alias'


class UnboundFieldError(ValueError):
    pass


class FieldDescriptor(cs.Subconstruct):  # noqa
    def __init__(self, subcon, name, default=M, validate=True):
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
        self.registry = {'bind': {}}
        self.get, self.set = _create_registry_api('bind', registry=self.registry)
        self._validate = validate

    def validate(self, instance, value):
        validate = instance.__validate__ and self._validate
        if not validate:
            self.subcon.build(value)  # mock build, raises an error
        return value

    def __get__(self, instance, owner):
        value = self.get(instance)
        if value is M:
            if isinstance(self.subcon, cs.Const):
                return self.subcon.value
            # if self.default is M:
            #     raise UnboundFieldError(self.name)
            return self.default
        return value

    def __set__(self, instance, value):
        print('set', instance, value)
        self.set(instance, self.validate(instance, value))

    def __truediv__(self, other):
        return cs.Renamed(self, other)
    __rtruediv__ = __truediv__


class DeclarativeConstruct:
    __setup__ = True
    __validate__ = True

    def __new__(cls, **args):
        if get_construct(cls, quiet_if_missing=True) is M:
            return _spawn_subclass(cls, args)
        elif args:
            fields = get_fields(cls)
            if not fields:
                return _spawn_subclass(cls, args)
            self = object.__new__(cls)
            for key, val in args.items():
                if key not in fields:
                    raise ValueError(f'unexpected argument: {key!r} (no such field)')
                setattr(self, key, val)
            return self
        return object.__new__(cls)

    def __repr__(self):
        cls_name = type(self).__name__
        fields_fmt = ', '.join(f'{k}={v!r}' for k, v in get_fields(self, final=True).items())
        return cls_name + f'({fields_fmt})'


Struct = create_decl(cs.Struct)
Sequence = create_decl(cs.Sequence)
FocusedSeq = create_decl(cs.FocusedSeq, reserve_args=['parsebuildfrom'])
Union = create_decl(cs.Union, reserve_args=['parsefrom'])
Select = create_decl(cs.Select)
LazyStruct = create_decl(cs.LazyStruct)
