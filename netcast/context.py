from __future__ import annotations

import abc
import asyncio
import collections.abc
import contextlib
import queue

from netcast.toolkit.collections import AttributeDict, MemoryDict


class ModifyHandle:
    MISSING = object()

    @classmethod
    def call(cls, context, put=MISSING, remove=MISSING):
        """Anytime a context is going to be modified, this method is called."""


class Context(metaclass=abc.ABCMeta):
    """
    All context classes must derive from this class.
    Should not be used directly - choose a proper subclass instead (or create your own).
    If subclassing, remember to call :class:`ModifyHandle` in all modification methods
    in order to make modification hooks work.
    """


class ListContext(list, Context):
    """A list context of associated classes or instances."""

    def append(self, item):
        ModifyHandle.call(self, put=item)
        return super().append(item)

    def extend(self, other):
        ModifyHandle.call(self, remove=other)
        return super().extend(other)

    def insert(self, i, item):
        ModifyHandle.call(self, put=item)
        return super().insert(i, item)

    def pop(self, i=-1):
        with contextlib.suppress(IndexError):
            ModifyHandle.call(self, remove=self[i])
        return super().remove(i)

    def remove(self, item):
        ModifyHandle.call(self, remove=item)
        return super().remove(item)

    def __setitem__(self, i, item):
        ModifyHandle.call(self, put=item)
        return super().__setitem__(i, item)

    def __delitem__(self, i):
        with contextlib.suppress(IndexError):
            ModifyHandle.call(self, remove=self[i])
        return super().__delitem__(i)


class DequeContext(collections.deque, Context):
    def append(self, item):
        ModifyHandle.call(self, put=item)
        return super().append(item)

    def extend(self, other):
        ModifyHandle.call(self, remove=other)
        return super().extend(other)

    def insert(self, i, item):
        ModifyHandle.call(self, put=item)
        return super().insert(i, item)

    def pop(self, i=-1):
        with contextlib.suppress(IndexError):
            ModifyHandle.call(self, remove=self[i])
        return super().remove(i)

    def remove(self, item):
        ModifyHandle.call(self, remove=item)
        return super().remove(item)

    def __setitem__(self, i, item):
        ModifyHandle.call(self, put=item)
        return super().__setitem__(i, item)

    def __delitem__(self, i):
        with contextlib.suppress(IndexError):
            ModifyHandle.call(self, remove=self[i])
        return super().__delitem__(i)

    def appendleft(self, item):
        ModifyHandle.call(self, put=item)
        return super().appendleft(item)

    def extendleft(self, other):
        ModifyHandle.call(self, remove=other)
        return super().extendleft(other)

    def popleft(self):
        with contextlib.suppress(IndexError):
            ModifyHandle.call(self, remove=self[0])
        return super().popleft()


class DictContext(AttributeDict, Context):
    """A key-value (with key=attribute access) context of associated classes or instances."""

    def __setitem__(self, key, item):
        old = self.get(key, ModifyHandle.MISSING)
        ModifyHandle.call(self, put=(key, item, old))
        return super().__setitem__(key, item)


class MemoryDictContext(MemoryDict, Context):
    def __setitem__(self, key, item):
        # XXX transforming the key 3 times?
        old = self.get(self.transform_key(key), ModifyHandle.MISSING)
        super().__setitem__(key, item)
        ModifyHandle.call(self, put=(self.transform_key(key), item, old))


def _put_impl(put):
    def _put(self, item):
        ModifyHandle.call(self, put=item)
        return put(self, item)
    return _put


def _get_impl(get):
    def _get(self):
        item = get(self)
        ModifyHandle.call(self, remove=item)
        return item
    return _get


def _queue_context_class(queue_class):
    return type(
        queue_class.__name__,
        (queue_class, Context),
        {'_put': _put_impl(queue_class._put), '_get': _get_impl(queue_class._get)}
    )


QueueContext = _queue_context_class(queue.Queue)
PriorityQueueContext = _queue_context_class(queue.PriorityQueue)
LifoQueueContext = _queue_context_class(queue.LifoQueue)

AsyncioQueueContext = _queue_context_class(asyncio.Queue)
AsyncioPriorityQueueContext = _queue_context_class(asyncio.PriorityQueue)
AsyncioLifoQueueContext = _queue_context_class(asyncio.LifoQueue)
