from __future__ import annotations

import functools
import operator
import ssl
import threading
from typing import Any, ClassVar, Type, Callable, Final, Union

from netcast.context import *
from netcast.context import LocalHook
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
    'CAT',
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
    'DEFAULT_CONTEXT_CLASS',
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

CAT, AT = Type["ClassArrangement"], Type["Arrangement"]


def arrangement_init(self, descent=None):
    self.descent = descent


def _is_classmethod(cls, method):
    return getattr(method, '__self__', None) is cls


def bind_factory(context_class=None, *, factory: Union[Callable, None] = None):
    if context_class is not None:
        if not callable(factory):
            raise ValueError('factory must be a callable')
        _BaseArrangement._factory_registry[context_class] = factory
        return context_class
    return functools.partial(bind_factory, factory=factory)


DEFAULT_CONTEXT_CLASS = DictContext


class _BaseArrangement:
    _super_registry: Final[MemoryDict] = MemoryDict()
    """Helper dict for managing an arrangement's class attributes."""

    _factory_registry: Final[dict] = {}
    """For creating contexts."""

    context_class: ClassVar[Type[Context] | None] = None
    """Context class. Must derive from the abstract class :class:`Context`."""

    _context: Context | Any | None
    """A :class:`Context` object shared across members of a class arrangement."""

    inherit_context: bool | None = None
    """
    Indicates whether to inherit the context directly from the superclass
    or create a new context for this class and mark the upper as a supercontext.

    Defaults to True.
    """
    context_params = Params()

    @classmethod
    def _get_supercontext(cls):
        return _BaseArrangement._super_registry.get(cls.get_context())

    @classmethod
    def _set_supercontext(cls, context: Context, supercontext: Context | None, meet: bool = False):
        _BaseArrangement._super_registry[context] = supercontext
        meet and cls._connect_contexts(context, supercontext)

    @classmethod
    def _connect_contexts(cls, context: Context, supercontext: Context | None = None):
        if supercontext is None:
            supercontext = _BaseArrangement._super_registry.get(context)
        if supercontext is not None:
            context._visit_supercontext(supercontext)
            supercontext._visit_subcontext(context)

    @classmethod
    def _create_context(cls, supercontext=None, context_class=None, self=None) -> Any:
        """Create a new context associated with its descent, :param:`supercontext`."""
        if context_class is None:
            context_class = cls.context_class

        context = create_context(context_class, cls if self is None else self, cls.context_params)
        cls._set_supercontext(context, supercontext)
        return context

    @classmethod
    def get_context(cls, *args, **kwargs):
        """Get the current context."""
        return getattr(cls, '_context', None)


class ClassArrangement(_BaseArrangement):
    """
    An arrangement of classes bound to a :class:`Context` object.

    When :class:`ClassArrangement` is subclassed, that subclass enters a new context.
    All its subclasses then may inherit it and then modify this context.

    When :class:`ClassArrangement` subclass' subclass has set `inherit_context` to False,
    then a new context is bound to it. The last subclass accesses the top-level context using
    `supercontext` property and the further subclasses access one context further so on.

    Note that it might be especially useful if those classes are singletons,
    however you may use :class:`Arrangement` for instance-context arrangements.
    Instances that participate in an instance arrangement must be given their descent.
    """
    descent_type: Type[ClassArrangement] | None
    _default_context_class = True

    @classmethod
    def context_wrapper(cls, context):
        yield context

    @classmethod
    def _get_inherit_context(cls):
        if cls.inherit_context is None:
            return True

        return cls.inherit_context

    @classmethod
    def _get_context_class(cls, context_class=None, inherit_context=None, descent=None):
        args = (context_class, cls.context_class)

        if None not in args and operator.is_not(*args):
            raise ValueError('context_class= set both when subclassing and in a subclass')

        descent_context_class = getattr(descent, 'context_class', context_class)

        if any(args):
            context_class, = filter(None, args)

        if context_class is None and descent_context_class is None:
            context_class = DEFAULT_CONTEXT_CLASS

        root_context_class: type | None = context_class

        if context_class is None:
            context_class = descent_context_class
            cls._default_context_class = False

        if (
                descent is not None
                and inherit_context
                and None not in (root_context_class, descent_context_class)
        ):
            root_context_class: type
            descent_context_class: type
            if not issubclass(root_context_class, descent_context_class):
                raise TypeError(
                    'context_class is different for descent and this class '
                    '(inherit_context = False may fix this error)'
                )

        cls.context_class = context_class
        return context_class

    def __init_subclass__(
            cls,
            descent=None,
            clear_init=False,
            context_class=None,
            family=False,
            irregular=False,
            _generate=True,
            _check_descent_type=True,
    ):
        """When a new subclass is created, handle its access to the local context."""
        if getattr(cls, '_context_lock', None) is None:
            cls._context_lock = threading.RLock()

        if irregular:
            return

        if descent is None:
            descent = cls.__base__

        cls.descent_type = descent

        inherit_context = cls._get_inherit_context()
        if _check_descent_type:
            context_class = cls._get_context_class(
                context_class,
                inherit_context and not family,
                descent
            )
        else:
            context_class = cls._get_context_class(context_class)
        assert issubclass(context_class, Context)

        if family:
            cls.inherit_context = None
            return

        context = descent.get_context()
        null_context = context is None

        if null_context:
            context = cls._create_context()

        if inherit_context or null_context:
            cls._context = context
        else:
            cls._context = cls._create_context(context)

        cls.inherit_context = None

        if _generate and not LocalHook.is_prepared(context):
            context = cls.get_context()
            context_wrapper = cls.context_wrapper
            if not _is_classmethod(cls, cls.context_wrapper):
                context_wrapper = functools.partial(context_wrapper, cls)
            original_context = context
            cls._context = next(context_wrapper(context), original_context)

        if clear_init:
            cls.__init__ = arrangement_init

    @property
    def context(self) -> Context | Any:
        """Get the current context. Note: this is the proper API for modifying it."""
        return self.get_context()

    @property
    def supercontext(self) -> Context | Any | None:
        """Get the current supercontext. Note: this is the proper API for modifying it."""
        return self._get_supercontext()

    @property
    def inherits_context(self) -> bool:
        return self.inherit_context


class Arrangement(ClassArrangement, irregular=True):
    # TODO: context wrappers fail

    descent: Arrangement | None
    _inherits_context = True
    _generate = True

    def __init__(self, descent=None):
        arrangement_init(self, descent)

    def __init_subclass__(
            cls,
            descent=None,
            clear_init=False,
            context_class=None,
            family=False,
            irregular=False,
            _generate=_generate,
            **kwargs
    ):
        if irregular:
            return

        context_class = cls._get_context_class(context_class)
        inherit_context = cls._get_inherit_context()

        cls.context_class = None
        cls.inherit_context = True

        super().__init_subclass__(
            descent=descent, clear_init=clear_init,
            context_class=MemoryDictContext, family=family, irregular=irregular,
            _generate=False, _check_descent_type=False,
        )

        cls.context_class = context_class
        cls._inherits_context = inherit_context
        cls._generate = _generate

    def __new__(cls, *args, **kwargs):
        if args:
            descent, *args = args
        else:
            descent = None

        inherit_context = cls._inherits_context

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

        if inherit_context and descent is not None:
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
                unprepared = LocalHook.is_prepared(context)
                if unprepared:
                    context_wrapper = cls.context_wrapper
                    if (
                            _is_classmethod(cls, context_wrapper)
                            or isinstance(context_wrapper, staticmethod)
                    ):
                        context_wrapper = functools.partial(context_wrapper)
                    else:
                        context_wrapper = functools.partial(context_wrapper, self)
                    original_context = context
                    contexts[self] = context = next(context_wrapper(context), original_context)
                    LocalHook.on_prepare(context)

        cls._connect_contexts(context)
        return self

    def context_wrapper(self, context):
        yield context

    @classmethod
    def get_context(cls, self=None):
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
    def context(self) -> Context | Any:
        """Get the current context. Note: this is the proper API for modifying it."""
        return self.get_context(self)

    @property
    def supercontext(self) -> Context | Any | None:
        """Get the current supercontext. Note: this is the proper API for modifying it."""
        return self._get_supercontext(self)

    @property
    def inherits_context(self) -> bool:
        return self._inherits_context


def create_context(context_class, cls_or_self, params=Params()):
    args, kwargs = params

    if callable(args):
        args = args(cls_or_self)

    if callable(kwargs):
        kwargs = kwargs(cls_or_self)

    factory = _BaseArrangement._factory_registry.get(context_class, context_class)
    return factory(*args, **kwargs)


def wrap_to_arrangement(name, context_class, class_arrangement=False, doc=None, env=None):
    if class_arrangement:
        super_class = ClassArrangement
    else:
        super_class = Arrangement

    if env is None:
        env = {}

    cls = type(name, (super_class,), env, family=True, context_class=context_class)
    doc and setattr(cls, '__doc__', doc)

    return cls


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
