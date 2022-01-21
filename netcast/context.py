from __future__ import annotations

import abc
import asyncio
import collections.abc
import dataclasses
import functools
import inspect
import io
import queue
import socket
import ssl
import sys
import threading
import warnings
from types import FunctionType, MethodType
from typing import Type, ForwardRef, Sequence, final, TypeVar, Iterable, Any, Callable

from netcast.toolkit.collections import AttributeDict, MemoryDict, MemoryList

CT, C = Type["Context"], ForwardRef("Context")


@dataclasses.dataclass
class ContextManagerPool:
    """Literally a context-manager pool."""
    per_class_cms: list[type]
    per_instance_cms: list = dataclasses.field(default_factory=list)
    methods: list = dataclasses.field(default_factory=list)

    def __post_init__(self):
        self._class_cms = MemoryDict()
        self._instance_cms = MemoryDict()
        self._method_cms = MemoryDict()

    def setup_context(self, context):
        for method in self.methods:
            self._method_cms.setdefault(context, {})
            for cm in self.per_class_cms:  # noo way, that can't be O(n^2) you little bastard
                self._method_cms[context].setdefault(method, [])
                self._method_cms[context][method].append(cm())
        else:
            if self.per_instance_cms and context not in self._instance_cms:
                for cm in self.per_class_cms:  # stop, ugh!
                    self._instance_cms.setdefault(context, [])
                    self._instance_cms[context].append(cm())
            elif self.per_class_cms and type(context) not in self._class_cms:
                for cm in self.per_class_cms:  # stop, ugh!
                    self._class_cms.setdefault(context, [])
                    self._class_cms[context].append(cm())

    def get_base_cms(self, context):
        if self.per_instance_cms:
            return self._instance_cms[context]
        return self._class_cms[type(context)]

    def get_cms(self, context, method_name=None):
        if method_name is None:
            return self.get_base_cms(context)

        if isinstance(method_name, (FunctionType, MethodType)):
            method_name = method_name.__name__

        if context in self._method_cms:
            cms = self._method_cms[context]
            if method_name in cms:
                return cms[method_name]

        return self.get_base_cms(context)

    @staticmethod
    def enter_one(cm):
        enter_value = None
        if cm is not None:
            enter_cm = getattr(cm, '__enter__', getattr(cm, '__aenter__', None))
            if callable(enter_cm):
                enter_value = enter_cm()
        return enter_value

    def enter(self, context, method_name=None):
        cms = self.get_cms(context, method_name=method_name)
        return list(map(self.enter_one, cms))

    @staticmethod
    def exit_one(cm, exc_info=(None, None, None)):
        exit_value = None
        if cm is not None:
            exit_cm = getattr(cm, '__exit__', getattr(cm, '__aexit__', None))
            if callable(exit_cm):
                exit_value = exit_cm(*exc_info)
        return exit_value

    def exit(self, context, method_name=None, initial_exc_info=(None, None, None)):
        sequence = self.get_cms(context, method_name=method_name)
        results = []

        def inner_exit(value, element):
            exit_value = None
            exc_values = value
            try:
                exit_value = self.exit_one(cm=element, exc_info=value)  # but it might be a coro!
            except Exception:
                exc_values = sys.exc_info()
            finally:
                results.append(exit_value)
                return exc_values

        functools.reduce(inner_exit, sequence=sequence, initial=initial_exc_info)
        return results


@final
class LocalHook:
    prepared_contexts = MemoryList()
    cm_pools = MemoryDict()
    listeners = MemoryDict()

    # Class LocalHook is final, shouldn't those below be static methods?
    @classmethod
    def precede_hook(cls, context, func, *args, **kwargs):
        """Anytime a context is going to be modified, this method is called."""
        pool = cls.cm_pools.get(context)
        if pool:
            pool.enter(context, func, sys.exc_info())

    @classmethod
    def finalize_hook(cls, context, func, *args, **kwargs):
        """Anytime a context was modified, this method is called."""
        pool = cls.cm_pools.get(context)
        if pool:
            pool.exit(context, func, sys.exc_info())

    @classmethod
    async def async_precede_hook(cls, context, func, *args, **kwargs):
        """Anytime a context is going to be modified asynchronously, this method is called."""
        pool = cls.cm_pools.get(context)
        if pool:
            enter_values = pool.enter(context, func)
            for enter_value in enter_values:
                if inspect.isawaitable(enter_value):
                    await enter_value

    @classmethod
    async def async_finalize_hook(cls, context, func, *args, **kwargs):
        """Anytime a context was modified asynchronously, this method is called."""
        pool = cls.cm_pools.get(context)
        if pool:
            exit_values = pool.exit(context, func)
            for exit_value in exit_values:
                if inspect.isawaitable(exit_value):
                    await exit_value

    @classmethod
    def is_prepared(cls, context):
        return context in cls.prepared_contexts

    @classmethod
    def on_prepare(cls, context):
        cls.prepared_contexts.append(context)
        lock_manager = cls.cm_pools.get(type(context))
        if lock_manager:
            lock_manager.setup_context(context)


def extend_cm_pool(
        context_class=None, *,
        per_class_cms=None,
        per_instance_cms=None,
        methods=None
):
    if context_class is None:
        return functools.partial(
            extend_cm_pool,
            per_class_cms=per_class_cms,
            per_instance_cms=per_instance_cms,
            methods=methods
        )
    pool = LocalHook.cm_pools.get(context_class)
    args = map(lambda arg: arg if arg else [], (per_class_cms, per_instance_cms, methods))
    if pool:
        per_class_cms, per_instance_cms, methods = args
        per_class_cms and pool.per_class_cms.extend(per_instance_cms)
        per_instance_cms and pool.per_instance_cms.extend(per_instance_cms)
        methods and pool.methods.extend(methods)
    else:
        per_class_cms, per_instance_cms, methods = map(
            lambda arg: arg if isinstance(arg, list) else list(arg),
            args
        )
        pool = ContextManagerPool(
            per_class_cms=per_class_cms,
            per_instance_cms=per_instance_cms,
            methods=methods
        )
        LocalHook.cm_pools[context_class] = pool
    return context_class


def append_cm_pool(context_class, cm_class, per_instance=True, methods=None, name=None):
    if name is None:
        name = 'CM' + context_class.__name__
    kwds = {}
    if methods:
        kwds = {'methods': methods}
    if per_instance:
        kwds.update(per_instance_cms=[cm_class])
    else:
        kwds.update(per_class_cms=[cm_class])
    return extend_cm_pool(type(name, (context_class,), {}), **kwds)


thread_safe = functools.partial(append_cm_pool, cm_class=threading.RLock)
greenlet_safe = functools.partial(append_cm_pool, cm_class=asyncio.Lock)


class Context(metaclass=abc.ABCMeta):
    """
    All context classes must derive from this class.

    If subclassing, remember to call :class:`ModifyHandle` in all modification methods
    in order to make modification hooks work
    (or use a built-in boilerplate saver, :func:`wrap_to_context`).
    """

    def _visit_supercontext(self, supercontext: Context):
        """Handle a supercontext. Handful for creating traversable context trees."""

    def _visit_subcontext(self, subcontext: Context):
        """Handle a subcontext. Handful for creating traversable context trees."""


_MISSING = object()
_WARN_ASYNC_HOOK = 'method must be async in order to invoke async hooks'


def _hooked_method(
        func: Callable,
        precede_hook: Callable | None = None,
        finalize_hook: Callable | None = None,
        cls: type | None = None
):
    if func is None:
        raise TypeError(
            f'method {func!r} '
            f'{"of " + repr(cls) + " " if cls is not None else ""}'
            f'does not exist'
        )

    if inspect.iscoroutinefunction(func):
        async def hooked_method_wrapper(self, *args, **kwargs):
            bound_method = getattr(self, func.__name__)
            if callable(precede_hook):
                pre_res = precede_hook(self, bound_method, *args, **kwargs)
                if inspect.isawaitable(pre_res):
                    await pre_res
            res = _MISSING
            try:
                res = await func(self, *args, **kwargs)
            finally:
                if callable(finalize_hook):
                    post_res = finalize_hook(self, bound_method, *args, **kwargs)
                    if inspect.isawaitable(post_res):
                        await post_res
                if res is _MISSING:
                    raise
                return res
    else:
        if inspect.iscoroutinefunction(precede_hook):
            warnings.warn(_WARN_ASYNC_HOOK, stacklevel=2)
        if inspect.iscoroutinefunction(finalize_hook):
            warnings.warn(_WARN_ASYNC_HOOK, stacklevel=2)

        def hooked_method_wrapper(self, *args, **kwargs):
            bound_method = getattr(self, func.__name__)
            if callable(precede_hook):
                precede_hook(self, bound_method, *args, **kwargs)
            res = _MISSING
            try:
                res = func(self, *args, **kwargs)
            finally:
                if callable(finalize_hook):
                    finalize_hook(self, bound_method, *args, **kwargs)
                if res is _MISSING:
                    raise
                return res

    return functools.update_wrapper(hooked_method_wrapper, func)


def _prepare_context_name(cls: type) -> str:
    class_name = cls.__name__
    suffix = 'Context'
    if class_name:
        first_letter = class_name[0].upper()
        if len(class_name) > 1:
            name = first_letter + class_name[1:] + suffix
        else:
            name = first_letter + suffix
    else:
        raise ValueError('class name was not provided')
    return name


_BT = TypeVar('_BT')


def wrap_to_context(
        bases: _BT,
        hooked_methods: Iterable | None = (),
        name: str | None = None,
        doc: str | None = None,
        init_subclass: dict[str, Any] | None = None
) -> _BT:
    """Build a context class and its modification hooks."""
    if isinstance(bases, Sequence):
        if not bases:
            raise ValueError('at least 1 base class is required')
        cls = bases[0]
        if len(bases) == 1:
            bases += (Context,)
    else:
        cls = bases
        bases = (cls, Context)
    env = {**({'__doc__': doc} if doc else {})}
    for method in hooked_methods:
        method = (
            getattr(cls, method, None)
            if isinstance(method, str)
            else method
        )
        if inspect.iscoroutinefunction(method):
            pre_hook = LocalHook.async_precede_hook
            post_hook = LocalHook.async_finalize_hook
        else:
            pre_hook = LocalHook.precede_hook
            post_hook = LocalHook.finalize_hook
        env[method.__name__] = _hooked_method(
            method, precede_hook=pre_hook,
            finalize_hook=post_hook, cls=cls
        )
    if name is None:
        name = _prepare_context_name(cls)
    if init_subclass is None:
        init_subclass = {}
    return type(name, bases, env, **init_subclass)


_list_hooked_methods = (
    'append', 'extend', 'insert', 'pop', 'remove', 'reverse', '__setitem__', '__delitem__'
)
_deque_hooked_methods = _list_hooked_methods + ('appendleft', 'extendleft', 'popleft')
_dict_hooked_methods = ('__setitem__',)
_queue_hooked_methods = ('_put', '_get', 'put', 'get')
_io_hooked_methods = ('write', 'read', 'seek', 'close')
_socket_hooked_methods = (
    'accept', 'bind', 'connect', 'connect_ex',
    'detach', 'recv', 'recvfrom', 'recv_into',
    'recvfrom_into', 'send', 'sendall', 'sendto',
    'setblocking', 'setsockopt', 'settimeout', 'sendfile',
    'shutdown',
)
_counter_hooked_methods = (
    'update', 'subtract', 'update', 'clear', '__ior__', '__iand__'
)

ListContext = wrap_to_context(list, _list_hooked_methods)
DequeContext = wrap_to_context(collections.deque, _deque_hooked_methods)
DictContext = wrap_to_context(AttributeDict, _dict_hooked_methods, name='DictContext')


class SupDirectedContextMixin(Context):
    """
    A context mixin that can access its supercontext via '_' key.
    You can set your own supercontext key, however.

    Used solely, it behaves like a linked list.
    """
    _supercontext_key = '_'

    def _visit_supercontext(self, supercontext):
        self[self._supercontext_key] = supercontext


class SingleSubDirectedContextMixin(Context):
    """
    A context that can access its subcontext via '__' key.
    You can set your own subcontext key, however.
    
    Used solely, it behaves like a linked list.
    """
    _subcontext_key = '__'

    def _visit_subcontext(self, subcontext):
        self[self._subcontext_key] = subcontext


class SubDirectedContextMixin(Context):
    """
    A context that can access its subcontexts via '__' key.
    You can set your own subcontexts key, however.
    """
    _subcontext_key = '__'

    def _visit_subcontext(self, subcontext):
        self.setdefault(self._subcontext_key, [])
        self[self._subcontext_key].append(subcontext)


class RootedTreeContextMixin(
    SupDirectedContextMixin,
    SubDirectedContextMixin
):
    """A context mixin that can be traversed like a rooted tree."""


class DoublyLinkedListContextMixin(
    SupDirectedContextMixin,
    SingleSubDirectedContextMixin
):
    """A context mixin that can be traversed like a doubly linked list."""


LinkedListContextMixin = SingleSubDirectedContextMixin
ConstructContext = wrap_to_context((
    SupDirectedContextMixin,
    AttributeDict,
    collections.OrderedDict
))
ByteArrayContext = wrap_to_context(bytearray, _list_hooked_methods, name='ByteArrayContext')
MemoryDictContext = wrap_to_context(MemoryDict, _dict_hooked_methods)
QueueContext = wrap_to_context(queue.Queue, _queue_hooked_methods)
PriorityQueueContext = wrap_to_context(queue.PriorityQueue, _queue_hooked_methods)
LifoQueueContext = wrap_to_context(queue.LifoQueue, _queue_hooked_methods)
AsyncioQueueContext = wrap_to_context(asyncio.Queue, _queue_hooked_methods, name='AsyncioQueueContext')  # noqa: E501
AsyncioPriorityQueueContext = wrap_to_context(asyncio.PriorityQueue, _queue_hooked_methods, name='AsyncioPriorityQueueContext')  # noqa: E501
AsyncioLifoQueueContext = wrap_to_context(asyncio.LifoQueue, _queue_hooked_methods, name='AsyncioLifoQueueContext')  # noqa: E501
FileIOContext = wrap_to_context(io.FileIO, _io_hooked_methods)
BytesIOContext = wrap_to_context(io.BytesIO, _io_hooked_methods)
StringIOContext = wrap_to_context(io.StringIO, _io_hooked_methods)
SocketContext = wrap_to_context(socket.socket, _socket_hooked_methods)
SSLSocketContext = wrap_to_context(ssl.SSLSocket, _socket_hooked_methods)
CounterContext = wrap_to_context(collections.Counter, _counter_hooked_methods)

# shortcuts
LContext = ListContext
DQContext = DequeContext
DContext = DictContext
BContext = ByteContext = BAContext = ByteArrayContext
MDContext = MemoryDictContext
QContext = QueueContext
PQContext = PriorityQueueContext
LQContext = LifoQueueContext
AQContext = AsyncioQueueContext
APQContext = AsyncioPriorityQueueContext
ALQContext = AsyncioLifoQueueContext
FIOContext = FileIOContext
BIOContext = BytesIOContext
SIOContext = StringIOContext
SockContext = SocketContext
SSLSockContext = SocketContext
CContext = CounterContext
