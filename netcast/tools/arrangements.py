from __future__ import annotations

import functools
import ssl
import threading
from typing import (
    Any,
    ClassVar,
    Type,
    Callable,
    Final,
    Union,
    TypeVar,
    Generator,
    Literal,
    cast,
)

from netcast.exceptions import ArrangementConstructionError, ArrangementTypeError
from netcast.tools.collections import IDLookupDictionary, Params, classproperty
from netcast.tools.contexts import *
from netcast.tools.inspection import is_classmethod

__all__ = (
    "AT",
    "Arrangement",
    "AsyncioLifoQueueArrangement",
    "AsyncioPriorityQueueArrangement",
    "AsyncioQueueArrangement",
    "ByteArrayArrangement",
    "BytesIOArrangement",
    "CT",
    "ClassArrangement",
    "ClassAsyncioLifoQueueArrangement",
    "ClassAsyncioPriorityQueueArrangement",
    "ClassAsyncioQueueArrangement",
    "ClassByteArrayArrangement",
    "ClassBytesIOArrangement",
    "ClassConstructArrangement",
    "ClassCounterArrangement",
    "ClassDequeArrangement",
    "ClassDictArrangement",
    "ClassFileIOArrangement",
    "ClassLifoQueueArrangement",
    "ClassListArrangement",
    "ClassPriorityQueueArrangement",
    "ClassQueueArrangement",
    "ClassSSLSocketArrangement",
    "ClassSocketArrangement",
    "ClassStringIOArrangement",
    "ConstructArrangement",
    "CounterArrangement",
    "CT_DEFAULT",
    "DequeArrangement",
    "DictArrangement",
    "FileIOArrangement",
    "LifoQueueArrangement",
    "ListArrangement",
    "PriorityQueueArrangement",
    "QueueArrangement",
    "SSLSocketArrangement",
    "SocketArrangement",
    "StringIOArrangement",
    "_BaseArrangement",
    "_init",
    "Arrangement",
    "AsyncioLifoQueueArrangement",
    "AsyncioPriorityQueueArrangement",
    "AsyncioQueueArrangement",
    "ByteArrayArrangement",
    "BytesIOArrangement",
    "ClassArrangement",
    "ClassAsyncioLifoQueueArrangement",
    "ClassAsyncioPriorityQueueArrangement",
    "ClassAsyncioQueueArrangement",
    "ClassByteArrayArrangement",
    "ClassBytesIOArrangement",
    "ClassCounterArrangement",
    "ClassDequeArrangement",
    "ClassDictArrangement",
    "ClassFileIOArrangement",
    "ClassLifoQueueArrangement",
    "ClassListArrangement",
    "ClassPriorityQueueArrangement",
    "ClassQueueArrangement",
    "ClassSSLSocketArrangement",
    "ClassSocketArrangement",
    "ClassStringIOArrangement",
    "CounterArrangement",
    "DequeArrangement",
    "DictArrangement",
    "FileIOArrangement",
    "LifoQueueArrangement",
    "ListArrangement",
    "PriorityQueueArrangement",
    "QueueArrangement",
    "SSLSocketArrangement",
    "SocketArrangement",
    "StringIOArrangement",
    "_init",
    "wrap_to_arrangement",
)

AT = TypeVar("AT", bound="ClassArrangement")
CT_DEFAULT = ConstructContext


def bind_factory(context_class: CT = None, *, factory: Union[Callable, None] = None):
    if context_class is not None:
        if not callable(factory):
            raise ValueError("factory must be a callable")
        _BaseArrangement._factory_registry[context_class] = factory
        return context_class
    return functools.partial(bind_factory, factory=factory)


def _init(self, descent=None):
    """Default arrangement constructor."""
    self.descent = descent


class _BaseArrangement:
    _super_registry: Final[ClassVar[IDLookupDictionary]] = IDLookupDictionary()
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
        return cls._super_registry.get(cls._get_context())

    @classmethod
    def _get_subcontexts(cls, self=None):
        registry = cls._super_registry
        subcontexts = []

        if self is None:
            context = cls._get_context()
        else:
            context = self.context

        for subcontext, supercontext in registry.items():
            if supercontext is context:
                subcontexts.append(registry.restore_key(subcontext))

        return tuple(subcontexts)

    @classmethod
    def _set_supercontext(
        cls, context: Context, supercontext: Context | None, bind: bool = False
    ):
        if context is supercontext:
            raise ValueError("no context can be a supercontext of itself")

        cls._super_registry[context] = supercontext
        if bind:
            cls._bind_contexts(context, supercontext)

    @classmethod
    def _bind_contexts(
        cls, context: Context, supercontext: Context | None = None, self=None
    ):
        if supercontext is None:
            supercontext = cls._super_registry.get(context)

        if self is None:
            self = cls

        if supercontext is not None:
            supercontext_key = getattr(self, "supercontext_key", None)
            if callable(supercontext_key):
                supercontext_key = supercontext_key(context, supercontext)

            subcontext_key = getattr(self, "subcontext_key", None)
            if callable(subcontext_key):
                subcontext_key = subcontext_key(context, supercontext)

            context._bind_supercontext(supercontext, final_key=supercontext_key)
            supercontext._bind_subcontext(context, final_key=subcontext_key)

    @classmethod
    def _create_context(
        cls, supercontext=None, context_class=None, self=None, bind=False
    ) -> CT:
        """Create a new context associated with its descent, :param:`supercontext`."""
        if context_class is None:
            context_class = cls.context_class

        context = create_context(
            context_class=context_class,
            cls_or_self=cls if self is None else self,
            params=cls.context_params
        )
        cls._set_supercontext(context, supercontext, bind=bind)

        return context

    @classmethod
    def _get_context(cls, *args, **kwargs) -> CT | None:
        """Get the current context."""
        return getattr(cls, "_context", None)


class ClassArrangement(_BaseArrangement):
    """
    An arrangement of classes bound to a :class:`Context` object.

    When :class:`ClassArrangement` is subclassed, that subclass might enter a new context.
    All its subclasses then may inherit it and then modify this context.
    Each following of that subclass instance can access a context common for the class
    of the instance, thus it is highly recommended wrapping the context class
    using :func:`thread_safe` or :func:`async_safe` function or use mutex locks programmatically.

    When :class:`ClassArrangement` subclass' subclass has set :attr:`new_context` to False,
    then a new context is bound to it. The last subclass accesses the top-level context using
    :attr:`supercontext` property and the further subclasses access one context further so on.

    Note that it might be especially useful if those classes are singletons,
    however you may use :class:`Arrangement` for instance-context arrangements.
    Instances that participate in an instance arrangement ought to be given their descent
    - arrangement participant that accesses a corresponding context.
    """

    _default_context_class = True

    descent_type: Type[ClassArrangement] | None
    supercontext_key: Any
    subcontext_key: Any

    @classmethod
    def _get_descent_type(cls):
        return getattr(cls, "descent_type", None)

    @classmethod
    def _get_new_context_flag(cls) -> bool:
        if cls.new_context is None:
            return False

        return cls.new_context

    @classmethod
    def _setup_context_class(
        cls, *, check_descent_type, context_class, new_context, config, descent=None
    ):
        if descent is None:
            descent = cls._get_descent_type()

        if check_descent_type:
            context_class = cls._resolve_context_class(
                context_class=context_class,
                new_context=new_context or config,
                descent=descent,
            )
        else:
            context_class = cls._resolve_context_class(context_class=context_class)

        assert issubclass(context_class, Context)
        return context_class

    @classmethod
    def _resolve_context_class(
        cls, *, context_class: Type[CT] | None = None, new_context=None, descent=None
    ) -> Type[CT]:
        if (
            context_class is not cls.context_class
            and context_class is not None
            and cls.context_class is not None
        ):
            raise ArrangementConstructionError(
                "context_class= set both when subclassing and in a subclass"
            )

        descent_context_class = getattr(descent, "context_class", context_class)

        if any((context_class, cls.context_class)):
            (context_class,) = filter(None, (context_class, cls.context_class))

        if context_class is None and descent_context_class is None:
            context_class = CT_DEFAULT

        if context_class is None:
            context_class = descent_context_class
            cls._default_context_class = False

        processed_context_class = context_class

        cls._check_context_class(
            processed_context_class=processed_context_class,
            descent_context_class=descent_context_class,
            descent=descent,
            new_context=new_context,
        )

        cls.context_class = context_class
        return context_class

    @classmethod
    def _check_context_class(
        cls,
        *,
        processed_context_class,
        descent_context_class,
        descent=None,
        new_context=None
    ):
        if descent is None:
            descent = cls._get_descent_type()

        if new_context is None:
            new_context = False

        if (
            descent is not None
            and not new_context
            and processed_context_class is not None
            and descent_context_class is not None
        ):
            if not issubclass(processed_context_class, descent_context_class):
                raise ArrangementConstructionError(
                    "context_class is different for descent and this class "
                    "(new_context = True may fix this error)"
                )

    @classmethod
    def _setup_context_access(cls, *, new_context, setup_context, descent=None):
        if descent is None:
            descent = cls._get_descent_type()

        context = descent._get_context()
        was_none = context is None

        if was_none:
            context = cls._create_context()

        if was_none or not new_context:
            cls._context = context
        else:
            cls._context = cls._create_context(context, bind=True)

        cls.new_context = None

        if setup_context:
            context = cls._call_setup_context()

        return context

    @classmethod
    def _call_setup_context(cls):
        context = cls._get_context()
        setup = cls.setup_context

        if not is_classmethod(cls, cls.setup_context):
            setup = functools.partial(setup, cls)

        cls._context = context = setup(context)
        return context

    @classmethod
    def _setup_context_lock(cls):
        lock = getattr(cls, "_context_lock", None)
        if lock is None:
            cls._context_lock = lock = threading.RLock()
        return lock

    @classmethod
    def _setup_descent_type(cls, *, descent=None):
        if descent is None:
            descent = cls.__base__

        cls.descent_type = descent
        return descent

    @classmethod
    def setup_context(cls, context) -> Generator[CT]:
        return context

    def __init_subclass__(
        cls,
        descent: AT | None = None,
        context_class: Type[CT] | None = None,
        config: bool = False,
        no_subclasshook: bool = False,
        setup_context: bool = True,
        check_descent_type: bool = True,
        clear_init: bool = False,
    ):
        """When a new subclass is created, handle its access to the local context."""
        if no_subclasshook:
            return

        new_context = cls._get_new_context_flag()

        cls._setup_descent_type(descent=descent)
        cls._setup_context_lock()
        cls._setup_context_class(
            check_descent_type=check_descent_type,
            context_class=context_class,
            new_context=new_context,
            config=config,
        )

        if config:
            return

        cls._setup_context_access(new_context=new_context, setup_context=setup_context)

        if clear_init:
            cls.__init__ = _init

    @classproperty
    def context(cls) -> CT | None:
        """Get the current context. Note: this is the proper API for modifying it."""
        return cls._get_context()

    @classproperty
    def supercontext(cls) -> Context | None:
        """Get the current supercontext. Note: this is the proper API for modifying it."""
        return cls._get_supercontext()

    @classproperty
    def subcontexts(cls) -> tuple[Context, ...] | None:
        return cls._get_subcontexts()

    @classproperty
    def has_new_context(cls) -> bool:
        return cls.new_context


class Arrangement(ClassArrangement, no_subclasshook=True):
    """
    An arrangement of instances bound to a :class:`Context` object.

    When :class:`Arrangement` is subclassed, that subclass then produces instances that access
    a distinct context. Each context is created per-instance, but instances may share
    their context with each other, when they are passed to the constructor.
    
    If :attr:`new_context` is set to `True` on a subclass, each instance will enter a subcontext
    of the context of the instance passed to the instance (called descent). 
    
    You might find arrangements useful for example if you want to maintain multiple connections.
    Having an arrangement class that uses context to store the connection data,
    you might create different instances to store per-connection, contextual data.
    Subcontexts might be a part of it, computing a certain branch of that data.
    """

    descent: Arrangement | None
    _new_context: bool = True
    _setup_context: bool = True

    def __init__(self, descent: Arrangement | None = None):
        _init(self, descent)

    def __init_subclass__(
        cls,
        descent: Arrangement | None = None,
        clear_init: bool = False,
        context_class: Type[CT] | None = None,
        config: bool = False,
        no_subclasshook: bool = False,
        setup_context: bool = _setup_context,
        check_descent_type: Literal[True] = True,
    ):
        if no_subclasshook:
            return

        context_class = cls._resolve_context_class(context_class=context_class)
        new_context = cls._get_new_context_flag()

        cls.context_class = None
        cls.new_context = False

        super().__init_subclass__(
            descent=descent,
            clear_init=clear_init,
            context_class=MemoryDictContext,
            config=config,
            no_subclasshook=no_subclasshook,
            setup_context=False,
            check_descent_type=False,
        )

        cls.context_class = context_class
        cls._new_context = new_context
        cls._setup_context = setup_context

    @classmethod
    def _resolve_descent(cls, args):
        if args:
            descent, *args = args
        else:
            descent = None
        return descent

    @classmethod
    def _get_descent(cls, args=(), validate_type=True):
        descent = cls._resolve_descent(args)
        expected_type = cls._get_descent_type()

        if validate_type and descent is not None and expected_type is not None:
            if not isinstance(descent, expected_type):
                raise ArrangementTypeError(
                    "passed descent's type " "and the fixed descent type are not equal"
                )

        return descent

    @classmethod
    def _setup_instance_context_access(cls, *, descent, contexts, self):
        new_context = cls._new_context

        if descent is not None and not new_context:
            context = contexts.get(descent)
            if context is None:
                context = descent.get_context()[descent]
            contexts[self] = context

        elif descent is not None:
            contexts[self] = cls._create_context(contexts[descent], self=self)

        else:
            contexts[self] = cls._create_context(self=self)

        context = contexts[self]

        if cls._setup_context:
            cls._instance_call_setup_context(
                context=context, contexts=contexts, self=self
            )
        cls._bind_contexts(context)

    @classmethod
    def _instance_call_setup_context(cls, *, context, contexts, self):
        with self._context_lock:
            setup = cls.setup_context
            if is_classmethod(cls, setup) or isinstance(setup, staticmethod):
                setup = functools.partial(setup)
            else:
                setup = functools.partial(setup, self)
            contexts[self] = setup(context)

    def __new__(cls, *args, **kwargs):
        descent = cls._get_descent(args)

        self = object.__new__(cls)
        _init(self, descent)

        contexts = cls._get_context()
        if contexts is None:
            raise ArrangementTypeError("abstract class")

        cls._setup_instance_context_access(
            descent=descent, contexts=contexts, self=self
        )
        return self

    def setup_context(self, context: CT) -> Generator[CT]:
        return context

    @classmethod
    def _get_context(cls, self: Arrangement | None = None) -> CT:
        """Get the current context."""
        contexts = super()._get_context()

        if self is None:
            return contexts

        return contexts[self]

    @classmethod
    def _get_supercontext(cls, self=None):
        """Get the current supercontext."""
        if self is None:
            return super()._get_supercontext()

        return _BaseArrangement._super_registry.get(cls._get_context(self))

    @property
    def context(self: Arrangement) -> CT | None:
        """Get the current context. Note: this is the proper API for modifying it."""
        return self._get_context(self)

    @property
    def supercontext(self: Arrangement) -> Context | None:
        """Get the current supercontext. Note: this is the proper API for modifying it."""
        return self._get_supercontext(self)

    @property
    def subcontexts(self: Arrangement) -> tuple[Context, ...] | None:
        return self._get_subcontexts(self)

    @property
    def has_new_context(self: Arrangement) -> bool:
        return self._new_context


def create_context(*, context_class: Type[CT], cls_or_self, params=Params()) -> CT:
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
    env: dict[str, Any] | None = None,
) -> Type[ClassArrangement]:
    if class_arrangement:
        super_class = ClassArrangement
    else:
        super_class = Arrangement

    if env is None:
        env = {}

    cls = type(name, (super_class,), env, config=True, context_class=context_class)
    doc and setattr(cls, "__doc__", doc)
    return cast(Type[ClassArrangement], cls)


_ = wrap_to_arrangement

ClassDictArrangement = _("ClassDictArrangement", DictContext, True)
ClassListArrangement = _("ClassListArrangement", ListContext, True)
ClassByteArrayArrangement = _("ClassByteArrayArrangement", ByteArrayContext, True)
ClassDequeArrangement = _("ClassDequeArrangement", DequeContext, True)
ClassQueueArrangement = _("ClassQueueArrangement", QueueContext, True)
ClassLifoQueueArrangement = _("ClassLifoQueueArrangement", LifoQueueContext, True)
ClassPriorityQueueArrangement = _(
    "ClassPriorityQueueArrangement", PriorityQueueContext, True
)
ClassAsyncioQueueArrangement = _(
    "ClassAsyncioQueueArrangement", AsyncioQueueContext, True
)
ClassAsyncioLifoQueueArrangement = _(
    "ClassAsyncioLifoQueueArrangement", AsyncioLifoQueueContext, True
)
ClassAsyncioPriorityQueueArrangement = _(
    "ClassAsyncioPriorityQueueArrangement", AsyncioPriorityQueueContext, True
)
ClassBytesIOArrangement = _("ClassBytesIOArrangement", BytesIOContext, True)
ClassStringIOArrangement = _("ClassStringIOArrangement", StringIOContext, True)
ClassFileIOArrangement = _("ClassFileIOArrangement", FileIOContext, True)
ClassSocketArrangement = _("ClassSocketArrangement", SocketContext, True)
SSLSocketContext = bind_factory(SSLSocketContext, factory=ssl.wrap_socket)
ClassSSLSocketArrangement = _("ClassSSLSocketArrangement", SSLSocketContext, True)
ClassCounterArrangement = _("ClassCounterArrangement", CounterContext, True)
ClassConstructArrangement = _("ClassConstructArrangement", ConstructContext, True)

DictArrangement = _("DictArrangement", DictContext)
ListArrangement = _("ListArrangement", ListContext)
ByteArrayArrangement = _("ByteArrayArrangement", ByteArrayContext)
DequeArrangement = _("DequeArrangement", DequeContext)
QueueArrangement = _("QueueArrangement", QueueContext)
LifoQueueArrangement = _("LifoQueueArrangement", LifoQueueContext)
PriorityQueueArrangement = _("PriorityQueueArrangement", PriorityQueueContext)
AsyncioQueueArrangement = _("AsyncioQueueArrangement", AsyncioQueueContext)
AsyncioLifoQueueArrangement = _("AsyncioLifoQueueArrangement", AsyncioLifoQueueContext)
AsyncioPriorityQueueArrangement = _(
    "AsyncioPriorityQueueArrangement", AsyncioPriorityQueueContext
)
FileIOArrangement = _("FileIOArrangement", FileIOContext)
BytesIOArrangement = _("BytesIOArrangement", BytesIOContext)
StringIOArrangement = _("StringIOArrangement", StringIOContext)
SocketArrangement = _("SocketArrangement", SocketContext)
SSLSocketArrangement = _("SSLSocketArrangement", SSLSocketContext)
CounterArrangement = _("CounterArrangement", CounterContext)
ConstructArrangement = _("ConstructArrangement", ConstructContext)
