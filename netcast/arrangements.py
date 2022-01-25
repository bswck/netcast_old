from __future__ import annotations

import ctypes
import functools
import operator
import ssl
import threading
from typing import (
    Any, ClassVar, Type, Callable, Final, Union, TypeVar, Generic, Generator, Literal
)

from netcast.contexts import *
from netcast.contexts import LocalHook  # noqa
from netcast.toolkit.collections import MemoryDict, Params


__all__ = (
    'AT',
    'ALQArrangement',
    'APQArrangement',
    'AQArrangement',
    'Arrangement',
    'AsyncioLifoQueueArrangement',
    'AsyncioPriorityQueueArrangement',
    'AsyncioQueueArrangement',
    'BAArrangement',
    'BIOArrangement',
    'ByteArrangement',
    'ByteArrayArrangement',
    'BytesIOArrangement',
    'CT',
    'CALQArrangement',
    'CAPQArrangement',
    'CAQArrangement',
    'CArrangement',
    'CBAArrangement',
    'CBIOArrangement',
    'CByteArrangement',
    'CDArrangement',
    'CDQArrangement',
    'CFIOArrangement',
    'CLArrangement',
    'CLQArrangement',
    'CPQArrangement',
    'CQArrangement',
    'CSArrangement',
    'CSIOArrangement',
    'CSSLSockArrangement',
    'ClassArrangement',
    'ClassAsyncioLifoQueueArrangement',
    'ClassAsyncioPriorityQueueArrangement',
    'ClassAsyncioQueueArrangement',
    'ClassByteArrayArrangement',
    'ClassBytesIOArrangement',
    'ClassConstructArrangement',
    'ClassCounterArrangement',
    'ClassDequeArrangement',
    'ClassDictArrangement',
    'ClassFileIOArrangement',
    'ClassLifoQueueArrangement',
    'ClassListArrangement',
    'ClassPriorityQueueArrangement',
    'ClassQueueArrangement',
    'ClassSSLSocketArrangement',
    'ClassSocketArrangement',
    'ClassStringIOArrangement',
    'ConstructArrangement',
    'CounterArrangement',
    'CT_DEFAULT',
    'DArrangement',
    'DQArrangement',
    'DequeArrangement',
    'DictArrangement',
    'FIOArrangement',
    'FileIOArrangement',
    'LArrangement',
    'LQArrangement',
    'LifoQueueArrangement',
    'ListArrangement',
    'PQArrangement',
    'PriorityQueueArrangement',
    'QArrangement',
    'QueueArrangement',
    'SArrangement',
    'SIOArrangement',
    'SSLSockArrangement',
    'SSLSocketArrangement',
    'SocketArrangement',
    'StringIOArrangement',
    '_BaseArrangement',
    'arrangement_init',
    'ALQArrangement',
    'APQArrangement',
    'AQArrangement',
    'Arrangement',
    'AsyncioLifoQueueArrangement',
    'AsyncioPriorityQueueArrangement',
    'AsyncioQueueArrangement',
    'BAArrangement',
    'BIOArrangement',
    'ByteArrangement',
    'ByteArrayArrangement',
    'BytesIOArrangement',
    'CALQArrangement',
    'CAPQArrangement',
    'CAQArrangement',
    'CArrangement',
    'CBAArrangement',
    'CBIOArrangement',
    'CByteArrangement',
    'CDArrangement',
    'CDQArrangement',
    'CFIOArrangement',
    'CLArrangement',
    'CLQArrangement',
    'CPQArrangement',
    'CQArrangement',
    'CSArrangement',
    'CSIOArrangement',
    'CSSLSockArrangement',
    'ClassArrangement',
    'ClassAsyncioLifoQueueArrangement',
    'ClassAsyncioPriorityQueueArrangement',
    'ClassAsyncioQueueArrangement',
    'ClassByteArrayArrangement',
    'ClassBytesIOArrangement',
    'ClassCounterArrangement',
    'ClassDequeArrangement',
    'ClassDictArrangement',
    'ClassFileIOArrangement',
    'ClassLifoQueueArrangement',
    'ClassListArrangement',
    'ClassPriorityQueueArrangement',
    'ClassQueueArrangement',
    'ClassSSLSocketArrangement',
    'ClassSocketArrangement',
    'ClassStringIOArrangement',
    'CounterArrangement',
    'DArrangement',
    'DQArrangement',
    'DequeArrangement',
    'DictArrangement',
    'FIOArrangement',
    'FileIOArrangement',
    'LArrangement',
    'LQArrangement',
    'LifoQueueArrangement',
    'ListArrangement',
    'PQArrangement',
    'PriorityQueueArrangement',
    'QArrangement',
    'QueueArrangement',
    'SArrangement',
    'SIOArrangement',
    'SSLSockArrangement',
    'SSLSocketArrangement',
    'SocketArrangement',
    'StringIOArrangement',
    'arrangement_init',
    'wrap_to_arrangement'
)


AT = TypeVar('AT', bound='ClassArrangement')
CT_DEFAULT = ConstructContext


def _is_classmethod(cls, method):
    return getattr(method, '__self__', None) is cls


def arrangement_init(self, descent=None):
    self.descent = descent


def bind_factory(
        context_class: CT = None,
        *, factory: Union[Callable, None] = None
):
    if context_class is not None:
        if not callable(factory):
            raise ValueError('factory must be a callable')
        _BaseArrangement._factory_registry[context_class] = factory
        return context_class
    return functools.partial(bind_factory, factory=factory)


class _BaseArrangement(Generic[CT]):
    _super_registry: Final[ClassVar[MemoryDict]] = MemoryDict()
    """Helper dict for managing an arrangement's class attributes."""

    _factory_registry: Final[dict] = {}
    """For creating contexts."""

    context_class: ClassVar[Type[Context] | None] = None
    """Context class. Must derive from the abstract class :class:`Context`."""

    _context: CT | None
    """A :class:`Context` object shared across members of a class arrangement."""

    new_context: bool | None = None
    """
    Indicates whether to inherit the context directly from the superclass
    or create a new context for this class and mark the upper as a supercontext.

    Defaults to False.
    """
    context_params = Params()

    @classmethod
    def _get_supercontext(cls):
        return _BaseArrangement._super_registry.get(cls.get_context())

    @classmethod
    def _get_subcontexts(cls, self=None):
        registry = _BaseArrangement._super_registry
        subcontexts = []
        if self is None:
            context = cls.get_context()
        else:
            context = self.context
        for subcontext, supercontext in registry.items():
            if supercontext is context:
                # TODO: is it safe?
                subcontexts.append(ctypes.cast(subcontext, ctypes.py_object).value)
        return tuple(subcontexts)

    @classmethod
    def _set_supercontext(
            cls, 
            context: Context, 
            supercontext: Context | None, 
            connect: bool = False
    ):
        if context is supercontext:
            raise ValueError('no context can be a supercontext of itself')
        _BaseArrangement._super_registry[context] = supercontext
        connect and cls._connect_contexts(context, supercontext)

    @classmethod
    def _connect_contexts(
            cls, 
            context: Context, 
            supercontext: Context | None = None,
            self=None
    ):
        if supercontext is None:
            supercontext = _BaseArrangement._super_registry.get(context)
        if self is None:
            self = cls
        if supercontext is not None:
            supercontext_key = getattr(self, 'supercontext_key', None)
            if callable(supercontext_key):
                supercontext_key = supercontext_key(context, supercontext)
            subcontext_key = getattr(self, 'subcontext_key', None)
            if callable(subcontext_key):
                subcontext_key = subcontext_key(context, supercontext)
            context._connect_supercontext(supercontext, final_key=supercontext_key)
            supercontext._connect_subcontext(context, final_key=subcontext_key)

    @classmethod
    def _create_context(
            cls,
            supercontext=None,
            context_class=None,
            self=None,
            connect=False
    ) -> CT:
        """Create a new context associated with its descent, :param:`supercontext`."""
        if context_class is None:
            context_class = cls.context_class

        context = create_context(context_class, cls if self is None else self, cls.context_params)
        cls._set_supercontext(context, supercontext, connect=connect)
        return context

    @classmethod
    def get_context(cls, *args, **kwargs) -> CT | None:
        """Get the current context."""
        return getattr(cls, '_context', None)


class ClassArrangement(_BaseArrangement, Generic[CT]):
    """
    An arrangement of classes bound to a :class:`Context` object.

    When :class:`ClassArrangement` is subclassed, that subclass enters a new context.
    All its subclasses then may inherit it and then modify this context.

    When :class:`ClassArrangement` subclass' subclass has set `new_context` to False,
    then a new context is bound to it. The last subclass accesses the top-level context using
    `supercontext` property and the further subclasses access one context further so on.

    Note that it might be especially useful if those classes are singletons,
    however you may use :class:`Arrangement` for instance-context arrangements.
    Instances that participate in an instance arrangement must be given their descent.
    """
    _default_context_class = True

    descent_type: Type[ClassArrangement] | None
    supercontext_key: Any
    subcontext_key: Any

    @classmethod
    def _get_new_context(cls) -> bool:
        if cls.new_context is None:
            return False

        return cls.new_context

    @classmethod
    def _get_context_class(
            cls,
            context_class: Type[CT] | None = None,
            new_context=None,
            descent=None
    ) -> Type[CT]:
        args = (context_class, cls.context_class)

        if None not in args and operator.is_not(*args):
            raise ValueError('context_class= set both when subclassing and in a subclass')

        descent_context_class = getattr(descent, 'context_class', context_class)

        if any(args):
            context_class, = filter(None, args)

        if context_class is None and descent_context_class is None:
            context_class = CT_DEFAULT

        processed_context_class: type | None = context_class

        if context_class is None:
            context_class = descent_context_class
            cls._default_context_class = False

        new_context = (False if new_context is None else new_context)
        if (
                descent is not None
                and not new_context
                and None not in (processed_context_class, descent_context_class)
        ):
            processed_context_class: Type[Context]
            descent_context_class: Type[Context]
            if not issubclass(processed_context_class, descent_context_class):
                raise TypeError(
                    'context_class is different for descent and this class '
                    '(new_context = True may fix this error)'
                )

        cls.context_class = context_class
        return context_class

    @classmethod
    def prepare_context(cls, context) -> Generator[CT]:
        yield context

    def __init_subclass__(
            cls,
            descent: AT | None = None,
            clear_init: bool = False,
            context_class: Type[CT] | None = None,
            config: bool = False,
            non_arrangement: bool = False,
            _generate: bool = True,
            _check_descent_type: bool = True,
    ):
        """When a new subclass is created, handle its access to the local context."""
        if getattr(cls, '_context_lock', None) is None:
            cls._context_lock = threading.RLock()

        if non_arrangement:
            return

        if descent is None:
            descent = cls.__base__

        cls.descent_type = descent

        new_context = cls._get_new_context()

        if _check_descent_type:
            context_class = cls._get_context_class(context_class, new_context or config, descent)
        else:
            context_class = cls._get_context_class(context_class)

        assert issubclass(context_class, Context)

        if config:
            return

        context = descent.get_context()
        null_context = context is None

        if null_context:
            context = cls._create_context()

        if null_context or not new_context:
            cls._context = context
        else:
            cls._context = cls._create_context(context, connect=True)

        cls.new_context = None

        if _generate and not LocalHook.is_prepared(context):
            context = cls.get_context()
            prepare_context = cls.prepare_context
            if not _is_classmethod(cls, cls.prepare_context):
                prepare_context = functools.partial(prepare_context, cls)
            original_context = context
            cls._context = next(prepare_context(context), original_context)
            LocalHook.on_prepare(context)

        if clear_init:
            cls.__init__ = arrangement_init

    @property
    def context(self: ClassArrangement[CT]) -> CT | None:
        """Get the current context. Note: this is the proper API for modifying it."""
        return self.get_context()

    @property
    def supercontext(self: ClassArrangement[CT]) -> Context | None:
        """Get the current supercontext. Note: this is the proper API for modifying it."""
        return self._get_supercontext()

    @property
    def subcontexts(self: ClassArrangement[CT]) -> tuple[Context, ...] | None:
        return self._get_subcontexts()

    @property
    def has_new_context(self: ClassArrangement[CT]) -> bool:
        return self.new_context


class Arrangement(ClassArrangement, Generic[CT], non_arrangement=True):
    # TODO: context wrappers fail

    descent: Arrangement | None
    _new_context: bool = True
    _generate: bool = True

    def __init__(self: Arrangement[CT], descent: Arrangement[CT] | None = None):
        arrangement_init(self, descent)

    def __init_subclass__(
            cls,
            descent: Arrangement | None = None,
            clear_init: bool = False,
            context_class: Type[CT] | None = None,
            config: bool = False,
            non_arrangement: bool = False,
            _generate: bool = _generate,
            _check_descent_type: Literal[True] = True
    ):
        if non_arrangement:
            return

        context_class = cls._get_context_class(context_class)
        new_context = cls._get_new_context()

        cls.context_class = None
        cls.new_context = False

        super().__init_subclass__(
            descent=descent, clear_init=clear_init,
            context_class=MemoryDictContext, config=config, non_arrangement=non_arrangement,
            _generate=False, _check_descent_type=False,
        )

        cls.context_class = context_class
        cls._new_context = new_context
        cls._generate = _generate

    def __new__(cls, *args, **kwargs):
        if args:
            descent, *args = args
        else:
            descent = None

        new_context = cls._new_context

        fixed_type = getattr(cls, 'descent_type', None)
        if None not in (descent, fixed_type):
            if not isinstance(descent, fixed_type):  # soft-check descent type
                raise TypeError(
                    'passed descent\'s type '
                    'and the fixed descent type are not equal'
                )

        contexts = cls.get_context()
        self = object.__new__(cls)
        arrangement_init(self, descent)

        if contexts is None:
            raise TypeError('abstract class')

        if not new_context and descent is not None:
            context = contexts.get(descent)
            if context is None:
                context = descent.get_context()[descent]
            contexts[self] = context
        elif descent is not None:
            contexts[self] = cls._create_context(contexts[descent], self=self)
        else:
            contexts[self] = cls._create_context(self=self)

        context = contexts[self]

        if cls._generate:

            with self._context_lock:
                unprepared = not LocalHook.is_prepared(context)
                if unprepared:
                    prepare_context = cls.prepare_context
                    if (
                            _is_classmethod(cls, prepare_context)
                            or isinstance(prepare_context, staticmethod)
                    ):
                        prepare_context = functools.partial(prepare_context)
                    else:
                        prepare_context = functools.partial(prepare_context, self)
                    original_context = context
                    contexts[self] = context = next(prepare_context(context), original_context)
                    LocalHook.on_prepare(context)

        cls._connect_contexts(context)
        return self

    def prepare_context(self, context: CT) -> Generator[CT]:
        yield context

    @classmethod
    def get_context(cls, self: Arrangement[CT] | None = None) -> CT:
        """Get the current context."""
        contexts = super().get_context()

        if self is None:
            return contexts

        return contexts[self]

    @classmethod
    def _get_supercontext(cls, self=None):
        """Get the current supercontext."""
        if self is None:
            return super()._get_supercontext()

        return _BaseArrangement._super_registry.get(cls.get_context(self))

    @property
    def context(self: Arrangement[CT]) -> CT | None:
        """Get the current context. Note: this is the proper API for modifying it."""
        return self.get_context(self)

    @property
    def supercontext(self: Arrangement[CT]) -> Context | None:
        """Get the current supercontext. Note: this is the proper API for modifying it."""
        return self._get_supercontext(self)

    @property
    def subcontexts(self: Arrangement[CT]) -> tuple[Context, ...] | None:
        return self._get_subcontexts(self)

    @property
    def has_new_context(self: Arrangement[CT]) -> bool:
        return self._new_context


def create_context(
        context_class: Type[CT],
        cls_or_self,
        params=Params()
) -> CT:
    args, kwargs = params

    if callable(args):
        args = args(cls_or_self)

    if callable(kwargs):
        kwargs = kwargs(cls_or_self)

    factory = _BaseArrangement._factory_registry.get(context_class, context_class)
    return factory(*args, **kwargs)


def wrap_to_arrangement(
        name: str,
        context_class: Type[CT],
        class_arrangement: bool = False,
        doc: str | None = None,
        env: dict[str, Any] | None = None
) -> Type[ClassArrangement]:
    if class_arrangement:
        super_class = ClassArrangement
    else:
        super_class = Arrangement

    if env is None:
        env = {}

    cls = type(name, (super_class,), env, config=True, context_class=context_class)
    cls.context: context_class  # noqa
    doc and setattr(cls, '__doc__', doc)

    return cls  # type: ignore


_ = wrap_to_arrangement

ClassDictArrangement = _('ClassDictArrangement', DictContext, True)
ClassListArrangement = _('ClassListArrangement', ListContext, True)
ClassByteArrayArrangement = _('ClassByteArrayArrangement', ByteArrayContext, True)
ClassDequeArrangement = _('ClassDequeArrangement', DequeContext, True)
ClassQueueArrangement = _('ClassQueueArrangement', QueueContext, True)
ClassLifoQueueArrangement = _('ClassLifoQueueArrangement', LifoQueueContext, True)
ClassPriorityQueueArrangement = _('ClassPriorityQueueArrangement', PriorityQueueContext, True)
ClassAsyncioQueueArrangement = _('ClassAsyncioQueueArrangement', AsyncioQueueContext, True)
ClassAsyncioLifoQueueArrangement = _(
    'ClassAsyncioLifoQueueArrangement', AsyncioLifoQueueContext, True
)
ClassAsyncioPriorityQueueArrangement = _(
    'ClassAsyncioPriorityQueueArrangement', AsyncioPriorityQueueContext, True
)
ClassBytesIOArrangement = _('ClassBytesIOArrangement', BytesIOContext, True)
ClassStringIOArrangement = _('ClassStringIOArrangement', StringIOContext, True)
ClassFileIOArrangement = _('ClassFileIOArrangement', FileIOContext, True)
ClassSocketArrangement = _('ClassSocketArrangement', SocketContext, True)
SSLSocketContext = bind_factory(SSLSocketContext, factory=ssl.wrap_socket)
ClassSSLSocketArrangement = _('ClassSSLSocketArrangement', SSLSocketContext, True)
ClassCounterArrangement = _('ClassCounterArrangement', CounterContext, True)
ClassConstructArrangement = _('ClassConstructArrangement', ConstructContext, True)

DictArrangement = _('DictArrangement', DictContext)
ListArrangement = _('ListArrangement', ListContext)
ByteArrayArrangement = _('ByteArrayArrangement', ByteArrayContext)
DequeArrangement = _('DequeArrangement', DequeContext)
QueueArrangement = _('QueueArrangement', QueueContext)
LifoQueueArrangement = _('LifoQueueArrangement', LifoQueueContext)
PriorityQueueArrangement = _('PriorityQueueArrangement', PriorityQueueContext)
AsyncioQueueArrangement = _('AsyncioQueueArrangement', AsyncioQueueContext)
AsyncioLifoQueueArrangement = _('AsyncioLifoQueueArrangement', AsyncioLifoQueueContext)
AsyncioPriorityQueueArrangement = _('AsyncioPriorityQueueArrangement', AsyncioPriorityQueueContext)
FileIOArrangement = _('FileIOArrangement', FileIOContext)
BytesIOArrangement = _('BytesIOArrangement', BytesIOContext)
StringIOArrangement = _('StringIOArrangement', StringIOContext)
SocketArrangement = _('SocketArrangement', SocketContext)
SSLSocketArrangement = _('SSLSocketArrangement', SSLSocketContext)
CounterArrangement = _('CounterArrangement', CounterContext)
ConstructArrangement = _('ConstructArrangement', ConstructContext)

# shortcuts
CArrangement = ClassArrangement
CDArrangement = ClassDictArrangement
CBAArrangement = CByteArrangement = ClassByteArrayArrangement
CLArrangement = ClassListArrangement
CDQArrangement = ClassDequeArrangement
CQArrangement = ClassQueueArrangement
CLQArrangement = ClassLifoQueueArrangement
CPQArrangement = ClassPriorityQueueArrangement
CAQArrangement = ClassAsyncioQueueArrangement
CALQArrangement = ClassAsyncioLifoQueueArrangement
CAPQArrangement = ClassAsyncioPriorityQueueArrangement
CBIOArrangement = ClassBytesIOArrangement
CSIOArrangement = ClassStringIOArrangement
CFIOArrangement = ClassFileIOArrangement
CSArrangement = ClassSocketArrangement
CSSLSockArrangement = ClassSSLSocketArrangement

DArrangement = DictArrangement
LArrangement = ListArrangement
BAArrangement = ByteArrangement = ByteArrayArrangement
DQArrangement = DequeArrangement
QArrangement = QueueArrangement
LQArrangement = LifoQueueArrangement
PQArrangement = PriorityQueueArrangement
AQArrangement = AsyncioQueueArrangement
ALQArrangement = AsyncioLifoQueueContext
APQArrangement = AsyncioPriorityQueueContext
BIOArrangement = BytesIOArrangement
SIOArrangement = StringIOArrangement
FIOArrangement = FileIOArrangement
SArrangement = SocketArrangement
SSLSockArrangement = SSLSocketArrangement
