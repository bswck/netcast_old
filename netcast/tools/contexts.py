from __future__ import annotations

import abc
import asyncio
import collections.abc
import functools
import inspect
import io
import queue
import socket
import ssl
import sys
import threading
import warnings
from typing import (
    MutableSequence,
    Sequence,
    TypeVar,
    Iterable,
    Any,
    Callable,
    Union,
    Type,
    Tuple,
)

from netcast.constants import MISSING
from netcast.exceptions import NetcastError
from netcast.tools import strings
from netcast.tools.collections import AttributeDict, IDLookupDictionary, Params


__all__ = (
    "AsyncioLifoQueueContext",
    "AsyncioPriorityQueueContext",
    "AsyncioQueueContext",
    "ByteArrayContext",
    "BytesIOContext",
    "CT",
    "ConstructContext",
    "Context",
    "ExitPool",
    "CounterContext",
    "DequeContext",
    "DictContext",
    "DoublyLinkedListContextMixin",
    "FileIOContext",
    "LifoQueueContext",
    "LinkedListContextMixin",
    "ListContext",
    "MemoryDictContext",
    "PriorityQueueContext",
    "QueueContext",
    "RootedTreeContextMixin",
    "SSLSocketContext",
    "SinglyDownwardContextMixin",
    "SocketContext",
    "StringIOContext",
    "DownwardContextMixin",
    "UpwardContextMixin",
    "wrap_method",
    "wrap_to_context",
)


class ExitPool:
    """Literally a context-manager pool."""

    def __init__(self, per_class_cms, per_instance_cms=None, methods=None):
        if per_instance_cms is None:
            per_instance_cms = []
        if methods is None:
            methods = []

        self.per_class_cms = per_class_cms
        self.per_instance_cms = per_instance_cms
        self.methods = methods

        self._class_cms = IDLookupDictionary()
        self._instance_cms = IDLookupDictionary()
        self._method_cms = IDLookupDictionary()

    def setup_context(self, context):
        if self.methods:
            for method in self.methods:
                self._method_cms.setdefault(context, {})
                for context_mgr in self.per_class_cms:
                    cms = self._method_cms[context].setdefault(method, [])
                    cms.append(context_mgr())
        else:
            if self.per_instance_cms and context not in self._instance_cms:
                for context_mgr in self.per_class_cms:
                    cms = self._instance_cms.setdefault(context, [])
                    cms.append(context_mgr())
            elif self.per_class_cms and type(context) not in self._class_cms:
                for context_mgr in self.per_class_cms:
                    cms = self._class_cms.setdefault(context, [])
                    cms.append(context_mgr())

    def _get_cms(self, context):
        if self.per_instance_cms:
            return self._instance_cms[context]
        return self._class_cms[type(context)]

    def get_cms(self, context, method_name=None):
        if method_name is None:
            return self._get_cms(context)

        if hasattr(method_name, '__name__'):
            method_name = method_name.__name__

        if context in self._method_cms:
            cms = self._method_cms[context]
            if method_name in cms:
                return cms[method_name]

        return self._get_cms(context)

    def enter(self, context, method_name=None, async_=False):
        cms = self.get_cms(context, method_name=method_name)

        if async_:
            async def _bulk_enter():
                for cm in cms:
                    enter_result = _enter(cm)
                    if inspect.isawaitable(enter_result):
                        await enter_result
        else:
            def _bulk_enter():
                for cm in cms:
                    _enter(cm)

        return _bulk_enter()

    def exit(
            self,
            context,
            method_name=None,
            exc_info=None,
            async_=False
    ):
        cms = self.get_cms(context, method_name=method_name)
        cms.reverse()

        if exc_info is None:
            exc_info = sys.exc_info()

        if async_:
            async def _call_exit(_exc_info, cm):
                try:
                    trigger = _exit(cm=cm, exc_info=_exc_info)
                    if inspect.isawaitable(trigger):
                        await trigger
                except Exception:
                    _exc_info = sys.exc_info()
                finally:
                    return _exc_info

            async def _bulk_exit(_exc_info):
                for cm in cms:
                    _exc_info = await _call_exit(_exc_info, cm)

        else:
            def _call_exit(_exc_info, cm):
                try:
                    _exit(cm=cm, exc_info=_exc_info)
                except Exception:
                    _exc_info = sys.exc_info()
                finally:
                    return _exc_info

            def _bulk_exit(_exc_info):
                for cm in cms:
                    _exc_info = _call_exit(_exc_info, cm)

        return _bulk_exit(exc_info)


def _enter(cm):
    enter_result = None
    call_enter = getattr(cm, "__exit__", getattr(cm, "__aexit__", None))

    if callable(call_enter):
        enter_result = call_enter()

    return enter_result


def _exit(cm, exc_info=None):
    exit_result = None

    if exc_info is None:
        exc_info = sys.exc_info()

    call_exit = getattr(cm, "__exit__", getattr(cm, "__aexit__", None))

    if callable(call_exit):
        exit_result = call_exit(*exc_info)

    return exit_result


async def _call_observer_async(observer, context, params):
    try:
        trigger = observer(context, *params.args, **params.kwargs)
        if inspect.isawaitable(trigger):
            await trigger
    except Exception as e:
        raise NetcastError('(async?) observer failed') from e


def _call_observer(observer, context, params):
    try:
        params.call(observer, context)
    except Exception as e:
        raise NetcastError('observer failed') from e


class _HookCaller:
    pools = IDLookupDictionary()
    observers = IDLookupDictionary()

    def call_observers(self, context, params, async_=False):
        observers = self.observers.setdefault(context, [])
        trigger = None

        if async_:
            trigger = asyncio.gather(*(
                _call_observer_async(observer, context, params)
                for observer in observers
            ))
        else:
            for observer in observers:
                try:
                    _call_observer(observer, context, params)
                finally:
                    continue
        return trigger

    def precede_hook(self, context, func, /, *args, **kwargs):
        """Anytime a context is on the verge of being modified, this method is called."""
        pool = self.pools.get(context)
        if pool:
            pool.enter(context, func, sys.exc_info())
        params = Params(args, kwargs)
        self.call_observers(context, params)

    def finalize_hook(self, context, func, /, *args, **kwargs):
        """Anytime a context was modified, this method is called."""
        pool = self.pools.get(context)
        if pool:
            pool.exit(context, func, sys.exc_info())
        params = Params(args, kwargs)
        self.call_observers(context, params)

    async def precede_hook_async(self, context, func, /, *args, **kwargs):
        """Anytime a context is going to be modified asynchronously, this method is called."""
        pool = self.pools.get(context)
        if not pool:
            return
        params = Params(args, kwargs)
        await pool.enter(context, func, async_=True)
        await self.call_observers(context, params, async_=True)

    async def finalize_hook_async(self, context, func, /, *args, **kwargs):
        """Anytime a context was modified asynchronously, this method is called."""
        pool = self.pools.get(context)
        if not pool:
            return
        params = Params(args, kwargs)
        await pool.exit(context, func, async_=True)
        await self.call_observers(context, params, async_=True)


hook_caller = _HookCaller()


def extend_exit_pool(
    context_class=None, *, per_class_cms=None, per_instance_cms=None, methods=None
):
    if context_class is None:
        return functools.partial(
            extend_exit_pool,
            per_class_cms=per_class_cms,
            per_instance_cms=per_instance_cms,
            methods=methods,
        )
    pool = hook_caller.pools.get(context_class)
    args = map(
        lambda arg: arg if arg else [], (per_class_cms, per_instance_cms, methods)
    )
    if pool:
        per_class_cms, per_instance_cms, methods = args
        pool.per_class_cms.extend(per_class_cms)
        pool.per_instance_cms.extend(per_instance_cms)
        pool.methods.extend(methods)
    else:
        per_class_cms, per_instance_cms, methods = map(
            lambda arg: arg if isinstance(arg, list) else list(arg), args
        )
        pool = ExitPool(
            per_class_cms=per_class_cms,
            per_instance_cms=per_instance_cms,
            methods=methods,
        )
        hook_caller.pools[context_class] = pool
    return context_class


def append_exit_pool(context_class, cm_class, per_instance=True, methods=None, name=None):
    if name is None:
        name = "CM" + context_class.__name__
    kwds = {}
    if methods:
        kwds = {"methods": methods}
    if per_instance:
        kwds.update(per_instance_cms=[cm_class])
    else:
        kwds.update(per_class_cms=[cm_class])
    return extend_exit_pool(type(name, (context_class,), {}), **kwds)


thread_safe = functools.partial(append_exit_pool, cm_class=threading.RLock)
async_safe = functools.partial(append_exit_pool, cm_class=asyncio.Lock)


class Context(metaclass=abc.ABCMeta):
    """
    All context classes must derive from this class.

    If subclassing, remember to call :var:`hook_caller` gathering hooks in all modification methods
    in order to make modification hooks work (or use a built-in boilerplate reducer,
    :func:`wrap_to_context`).
    """

    def _bind_supercontext(self, supercontext: Context, final_key: Any | None = None):
        """Handle a supercontext. Handful for creating traversable context trees."""

    def _bind_subcontext(self, subcontext: Context, final_key: Any | None = None):
        """Handle a subcontext. Handful for creating traversable context trees."""


_WARN_ASYNC_HOOK = "method %s() must be async in order to invoke async hooks"


def wrap_method(
    func: Callable,
    precede_hook: Union[Callable, None] = None,
    finalize_hook: Union[Callable, None] = None,
    cls: type | None = None,
    precedential_reshaping: bool = False,
    hook_takes_method: bool = True,
    finalizer_takes_result: bool = False,
):
    if func is None:
        raise TypeError(
            f"method "
            f'{"of " + repr(cls) + " " if cls is not None else ""}'
            f"does not exist"
        )

    if inspect.iscoroutinefunction(func):

        async def wrapper(self, *args, **kwargs):
            bound_method = getattr(self, func.__name__)

            params = Params.pack(Params.pack(args=args, kwargs=kwargs))

            if hook_takes_method:
                params = Params.pack(bound_method, *params.args, **params.kwargs)

            if callable(precede_hook):
                trigger = reshaped = params.call(precede_hook, self)

                if inspect.isawaitable(trigger):
                    reshaped = await trigger

                if precedential_reshaping and isinstance(reshaped, Params):
                    args = (self, *reshaped.args)
                    kwargs = {**reshaped.kwargs}

            res = MISSING

            try:
                res = await func(self, *args, **kwargs)

            finally:
                if finalizer_takes_result:
                    params = Params.pack(res, *params.args, **params.kwargs)

                if callable(finalize_hook):
                    trigger = params.call(finalize_hook, self)
                    if inspect.isawaitable(trigger):
                        await trigger

                if res is MISSING:
                    raise  # pylint: disable=E0704

                return res  # pylint: disable=WO150

    else:
        if inspect.iscoroutinefunction(precede_hook):
            warnings.warn(
                _WARN_ASYNC_HOOK % strings.truncate(func.__name__), stacklevel=2
            )
        if inspect.iscoroutinefunction(finalize_hook):
            warnings.warn(
                _WARN_ASYNC_HOOK % strings.truncate(func.__name__), stacklevel=2
            )

        def wrapper(self, *args, **kwargs):
            bound_method = getattr(self, func.__name__)

            hook_kwargs = kwargs
            if hook_takes_method:
                hook_args = (self, bound_method)
            else:
                hook_args = (self,)
            hook_args += args

            if callable(precede_hook):
                reshaped = precede_hook(*hook_args, **hook_kwargs)

                if precedential_reshaping:
                    args, kwargs = reshaped

            result = MISSING

            try:
                result = func(self, *args, **kwargs)

            finally:
                if finalizer_takes_result:
                    if hook_takes_method:
                        hook_args = (self, bound_method, result)
                    else:
                        hook_args = (self, result)

                if callable(finalize_hook):
                    finalize_hook(*hook_args, **hook_kwargs)

                if result is MISSING:
                    raise  # pylint: disable=E0704

                return result  # pylint: disable=WO150

    return functools.update_wrapper(wrapper, func)


def _supply_context_name(cls: type) -> str:
    class_name = cls.__name__
    suffix = "Context"
    if class_name:
        first_letter = class_name[0].upper()
        if len(class_name) > 1:
            name = first_letter + class_name[1:] + suffix
        else:
            name = first_letter + suffix
    else:
        raise ValueError("class name was not provided")
    return name


BT = TypeVar("BT", type, Tuple[type, ...])


def wrap_to_context(
    bases: BT,
    hooked_methods: Iterable | None = (),
    name: str | None = None,
    doc: str | None = None,
    init_subclass: dict[str, Any] | None = None,
) -> Type[Context] | BT:
    """Build a context class and its modification hooks."""
    if isinstance(bases, Sequence):
        if not bases:
            raise ValueError("at least 1 base class is required")
        if Context not in bases:  # for safety
            bases += (Context,)
        cls = bases[0]
    else:
        cls = bases
        bases = (cls, Context)
    env = {**({"__doc__": doc} if doc else {})}
    for method in hooked_methods:
        method = getattr(cls, method, None) if isinstance(method, str) else method
        if inspect.iscoroutinefunction(method):
            precede_hook = hook_caller.precede_hook_async
            finalize_hook = hook_caller.finalize_hook_async
        else:
            precede_hook = hook_caller.precede_hook
            finalize_hook = hook_caller.finalize_hook
        env[method.__name__] = wrap_method(
            method, precede_hook=precede_hook, finalize_hook=finalize_hook, cls=cls
        )
    if name is None:
        name = _supply_context_name(cls)
    if init_subclass is None:
        init_subclass = {}
    return type(name, bases, env, **init_subclass)


_list_hooked_methods = (
    "append",
    "extend",
    "insert",
    "pop",
    "remove",
    "reverse",
    "__setitem__",
    "__delitem__",
)
_deque_hooked_methods = _list_hooked_methods + ("appendleft", "extendleft", "popleft")
_dict_hooked_methods = ("__setitem__",)
_queue_hooked_methods = ("_put", "_get", "put", "get")
_io_hooked_methods = ("write", "read", "seek", "close")
_socket_hooked_methods = (
    "accept",
    "bind",
    "connect",
    "connect_ex",
    "detach",
    "recv",
    "recvfrom",
    "recv_into",
    "recvfrom_into",
    "send",
    "sendall",
    "sendto",
    "setblocking",
    "setsockopt",
    "settimeout",
    "sendfile",
    "shutdown",
)
_counter_hooked_methods = (
    "update",
    "subtract",
    "update",
    "clear",
    "__ior__",
    "__iand__",
)

ListContext = wrap_to_context(list, _list_hooked_methods)
DequeContext = wrap_to_context(collections.deque, _deque_hooked_methods)
DictContext = wrap_to_context(AttributeDict, _dict_hooked_methods, name="DictContext")


class UpwardContextMixin(Context):
    """
    A context mixin that can access its supercontext via '_' key.
    You can set your own supercontext key, however.

    Used solely, it behaves like a linked list.
    """

    _supercontext_key: Any = "_"

    def _bind_supercontext(
        self: UpwardContextMixin | MutableSequence,
        supercontext: Context,
        final_key: _supercontext_key | None = None,
    ):
        if final_key is None:
            final_key = self._supercontext_key
        self[final_key] = supercontext


class SinglyDownwardContextMixin(Context):
    """
    A context that can access its subcontext via '__' key.
    You can set your own subcontext key, however.
    
    Used solely, it behaves like a linked list.
    """

    _subcontext_key: Any = "__"

    def _bind_subcontext(
        self: SinglyDownwardContextMixin | MutableSequence,
        subcontext: Context,
        final_key: _subcontext_key | None = None,
    ):
        if final_key is None:
            final_key = self._subcontext_key
        self[final_key] = subcontext


class DownwardContextMixin(Context):
    """
    A context that can access its subcontexts via '__' key.
    You can set your own subcontexts key, however.
    """

    _subcontext_key: Any = "__"

    def _bind_subcontext(
        self: DownwardContextMixin | MutableSequence,
        subcontext: Context,
        final_key: _subcontext_key | None = None,
    ):
        if final_key is None:
            final_key = self._subcontext_key
        if final_key not in self:
            self[final_key] = []
        self[final_key].append(subcontext)


class RootedTreeContextMixin(UpwardContextMixin, DownwardContextMixin):
    """A context mixin that can be traversed like a rooted tree."""


class DoublyLinkedListContextMixin(UpwardContextMixin, SinglyDownwardContextMixin):
    """A context mixin that can be traversed like a doubly linked list."""


LinkedListContextMixin = SinglyDownwardContextMixin

_ = wrap_to_context

ConstructContext = _((UpwardContextMixin, collections.OrderedDict, AttributeDict))
ByteArrayContext = _(bytearray, _list_hooked_methods, name="ByteArrayContext")
MemoryDictContext = _(IDLookupDictionary, _dict_hooked_methods)
QueueContext = _(queue.Queue, _queue_hooked_methods)
PriorityQueueContext = _(queue.PriorityQueue, _queue_hooked_methods)
LifoQueueContext = _(queue.LifoQueue, _queue_hooked_methods)
AsyncioQueueContext = _(
    asyncio.Queue, _queue_hooked_methods, name="AsyncioQueueContext"
)
AsyncioPriorityQueueContext = _(
    asyncio.PriorityQueue, _queue_hooked_methods, name="AsyncioPriorityQueueContext"
)
AsyncioLifoQueueContext = _(
    asyncio.LifoQueue, _queue_hooked_methods, name="AsyncioLifoQueueContext"
)
FileIOContext = _(io.FileIO, _io_hooked_methods)
BytesIOContext = _(io.BytesIO, _io_hooked_methods)
StringIOContext = _(io.StringIO, _io_hooked_methods)
SocketContext = _(socket.socket, _socket_hooked_methods)

SSLSocketContext = _(ssl.SSLSocket, _socket_hooked_methods)
CounterContext = _(collections.Counter, _counter_hooked_methods)

CT = TypeVar(
    "CT",
    Context,
    ListContext,
    DictContext,
    DequeContext,
    ConstructContext,
    ByteArrayContext,
    MemoryDictContext,
    QueueContext,
    PriorityQueueContext,
    LifoQueueContext,
    AsyncioQueueContext,
    AsyncioPriorityQueueContext,
    AsyncioLifoQueueContext,
    FileIOContext,
    BytesIOContext,
    StringIOContext,
    SocketContext,
    SSLSocketContext,
    CounterContext,
)
