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
import threading
import warnings
from ssl import SSLSocket
from types import FunctionType, MethodType
from typing import Type, ForwardRef, Sequence, final

from netcast.toolkit.collections import AttributeDict, MemoryDict, MemoryList

CT, C = Type["Context"], ForwardRef("Context")


@dataclasses.dataclass
class CMManager:
    """Literally a context-manager manager."""
    cm_class: type
    per_instance: bool = False
    methods: Sequence = dataclasses.field(default_factory=list)

    def __post_init__(self):
        if self.methods is None:
            self.methods = []
        self._class_cm = self.cm_class()
        self._instance_cms = MemoryDict()
        self._method_cms = MemoryDict()

    def setup_context(self, context):
        for method in self.methods:
            self._method_cms.setdefault(context, {})
            if method not in self._method_cms[context]:
                self._method_cms[context][method] = self.cm_class()
        else:
            if self.per_instance and context not in self._instance_cms:
                self._instance_cms[context] = self.cm_class()

    def get_base_cm(self, context):
        if self.per_instance:
            return self._instance_cms[context]
        return self._class_cm

    def get_cm(self, context, method_name=None):
        if method_name is None:
            return self.get_base_cm(context)

        if isinstance(method_name, (FunctionType, MethodType)):
            method_name = method_name.__name__

        if context in self._method_cms:
            cms = self._method_cms[context]
            if method_name in cms:
                return cms[method_name]

        return self.get_base_cm(context)

    def enter(self, context, method_name=None):
        lock = self.get_cm(context, method_name=method_name)
        entered = None
        if lock is not None:
            enter_cm = getattr(lock, '__enter__', getattr(lock, '__aenter__', None))
            if callable(enter_cm):
                entered = enter_cm()
        return entered

    def exit(self, context, method_name=None, exc_info=(None, None, None)):
        lock = self.get_cm(context, method_name=method_name)
        exitted = None
        if lock is not None:
            exit_cm = getattr(lock, '__exit__', getattr(lock, '__aexit__', None))
            if callable(exit_cm):
                exitted = exit_cm(*exc_info)
        return exitted


@final
class _LocalHook:
    prepared_contexts = MemoryList()
    cm_managers = MemoryDict()
    listeners = MemoryDict()

    # Class _LocalHook is final, shouldn't those below be static methods?
    @classmethod
    def pre_hook(cls, context, func, *args, **kwargs):
        """Anytime a context is going to be modified, this method is called."""

    @classmethod
    def post_hook(cls, context, func, *args, **kwargs):
        """Anytime a context was modified, this method is called."""

    @classmethod
    async def async_pre(cls, context, func, *args, **kwargs):
        """Anytime a context is going to be modified asynchronously, this method is called."""

    @classmethod
    async def async_post(cls, context, func, *args, **kwargs):
        """Anytime a context was modified asynchronously, this method is called."""

    @classmethod
    def is_prepared(cls, context):
        return context in cls.prepared_contexts

    @classmethod
    def on_prepare(cls, context):
        cls.prepared_contexts.append(context)
        lock_manager = cls.cm_managers.get(type(context))
        if lock_manager:
            lock_manager.setup_context(context)


def locked(context_class=None, *, cm_class, per_instance=True, methods=None):
    if context_class is None:
        return functools.partial(locked, lock_class=cm_class, per_instance=per_instance)
    cm_manager = _LocalHook.cm_managers.get(cm_class)
    if cm_manager:
        if methods:
            cm_manager.methods.extend(methods)
        cm_manager.per_instance = per_instance
    else:
        cm_manager = CMManager(
            cm_class=cm_class,
            per_instance=per_instance,
            methods=methods
        )
        _LocalHook.cm_managers[context_class] = cm_manager
    return context_class


def concurrency_safe(context_class, cm_class, per_instance=True, name=None):
    if name is None:
        name = 'Locked' + context_class.__name__
    return locked(type(name, (context_class,), {}), cm_class=cm_class, per_instance=per_instance)


thread_safe = functools.partial(concurrency_safe, cm_class=threading.RLock)
greenlet_safe = functools.partial(concurrency_safe, cm_class=asyncio.Lock)


class Context(metaclass=abc.ABCMeta):
    """
    All context classes must derive from this class.
    Should not be used directly - choose a proper subclass instead (or create your own).
    If subclassing, remember to call :class:`ModifyHandle` in all modification methods
    in order to make modification hooks work.
    """


_WARN_ASYNC_HOOK = 'method must be async in order to invoke async hooks'


def _hooked_method(func, pre_hook=None, post_hook=None, cls=None):
    if func is None:
        raise TypeError(
            f'method {func!r} '
            f'{"of " + repr(cls) + " " if cls is not None else ""}'
            f'does not exist'
        )

    if inspect.iscoroutinefunction(func):
        async def hooked_method_wrapper(self, *args, **kwargs):
            bound_method = getattr(self, func.__name__)
            if callable(pre_hook):
                pre_res = pre_hook(self, bound_method, *args, **kwargs)
                if inspect.isawaitable(pre_res):
                    await pre_res
            res = await func(self, *args, **kwargs)
            if callable(post_hook):
                post_res = post_hook(self, bound_method, *args, **kwargs)
                if inspect.isawaitable(post_res):
                    await post_res
            return res
    else:
        if inspect.iscoroutinefunction(pre_hook):
            warnings.warn(_WARN_ASYNC_HOOK, stacklevel=2)
        if inspect.iscoroutinefunction(post_hook):
            warnings.warn(_WARN_ASYNC_HOOK, stacklevel=2)

        def hooked_method_wrapper(self, *args, **kwargs):
            bound_method = getattr(self, func.__name__)
            if callable(pre_hook):
                pre_hook(self, bound_method, *args, **kwargs)
            res = func(self, *args, **kwargs)
            if callable(post_hook):
                post_hook(self, bound_method, *args, **kwargs)
            return res
    return functools.update_wrapper(hooked_method_wrapper, func)


def wrap_to_context(bases, hooked_methods=(), name=None, doc=None, init_subclass=None):
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
            pre_hook = _LocalHook.async_pre
            post_hook = _LocalHook.async_post
        else:
            pre_hook = _LocalHook.pre_hook
            post_hook = _LocalHook.post_hook
        env[method.__name__] = _hooked_method(
            method, pre_hook=pre_hook,
            post_hook=post_hook, cls=cls
        )
    if name is None:
        cls_name = cls.__name__
        suffix = 'Context'
        if cls_name:
            f = cls_name[0].upper()
            if len(cls_name) > 1:
                name = f + cls_name[1:] + suffix
            else:
                name = f + suffix
        else:
            raise ValueError('class name was not provided')
    if init_subclass is None:
        init_subclass = {}
    return type(name, bases, env, **init_subclass)


_list_modifiers = (
    'append', 'extend', 'insert', 'pop', 'remove', 'reverse', '__setitem__', '__delitem__'
)
_deque_modifiers = _list_modifiers + ('appendleft', 'extendleft', 'popleft')
_dict_modifiers = ('__setitem__',)
_queue_modifiers = ('_put', '_get', 'put', 'get')
_io_modifiers = ('write', 'read', 'seek', 'close')
_socket_modifiers = ('send', 'recv')

ListContext = wrap_to_context(list, _list_modifiers)
DequeContext = wrap_to_context(collections.deque, _deque_modifiers)
DictContext = wrap_to_context(AttributeDict, _dict_modifiers, name='DictContext')
ByteArrayContext = wrap_to_context(bytearray, _list_modifiers, name='ByteArrayContext')
MemoryDictContext = wrap_to_context(MemoryDict, _dict_modifiers)
QueueContext = wrap_to_context(queue.Queue, _queue_modifiers)
PriorityQueueContext = wrap_to_context(queue.PriorityQueue, _queue_modifiers)
LifoQueueContext = wrap_to_context(queue.LifoQueue, _queue_modifiers)
AsyncioQueueContext = wrap_to_context(asyncio.Queue, _queue_modifiers, name='AsyncioQueueContext')
AsyncioPriorityQueueContext = wrap_to_context(asyncio.PriorityQueue, _queue_modifiers, name='AsyncioPriorityQueueContext')  # noqa: E501
AsyncioLifoQueueContext = wrap_to_context(asyncio.LifoQueue, _queue_modifiers, name='AsyncioLifoQueueContext')  # noqa: E501
FileIOContext = wrap_to_context(io.FileIO, _io_modifiers)
BytesIOContext = wrap_to_context(io.BytesIO, _io_modifiers)
StringIOContext = wrap_to_context(io.StringIO, _io_modifiers)
SocketContext = wrap_to_context(socket.socket, _socket_modifiers)
SSLSocketContext = wrap_to_context(SSLSocket, _socket_modifiers)

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
