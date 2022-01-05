import asyncio
from typing import ClassVar

import pytest

from netcast.arrangement import DEFAULT_CONTEXT_CLASS, AT, CAT
from netcast.arrangement import (
    ClassArrangement, ClassFileIOArrangement,
    Arrangement, FileIOArrangement,
    ClassSSLSocketArrangement, SSLSocketArrangement
)
from netcast.context import C, CT
from netcast.toolkit.collections import Params, ForwardDependency

class_arrangements = {ClassArrangement, *ClassArrangement.__subclasses__()}
class_arrangements.discard(Arrangement)
class_arrangements.discard(ClassFileIOArrangement)
class_arrangements.discard(ClassSSLSocketArrangement)


@pytest.fixture(params=class_arrangements)
def ca(request) -> CAT:
    yield request.param


arrangements = {Arrangement, *Arrangement.__subclasses__()}
arrangements.discard(FileIOArrangement)
arrangements.discard(SSLSocketArrangement)


@pytest.fixture(params=arrangements)
def a(request) -> AT:
    yield request.param


class _TestContextType:
    context: C
    context_class: ClassVar[CT]

    def test(self, cls: CAT):
        if cls.context_class is None:
            expected_context_class = DEFAULT_CONTEXT_CLASS
        else:
            expected_context_class = cls.context_class
        assert type(self.context) is expected_context_class is self.context_class


class TestClassArrangement:
    def test_abstract(self):
        from netcast.context import ListContext

        class Abstract(ClassArrangement, abstract=True):
            context_class = ListContext

            def test(self):
                assert self.context is None

        class CA1(ClassArrangement, descent=Abstract):
            context_class = None

            def test(self):
                assert self.context_class is Abstract.context_class
                assert isinstance(self.context, Abstract.context_class)

        class CA2(Abstract):
            def test(self):
                assert isinstance(self.context, Abstract.context_class)

        from netcast.context import QueueContext as SomeOtherContext

        with pytest.raises(TypeError):
            # noinspection PyUnusedLocal
            class Unsafe(ClassArrangement, descent=Abstract):
                context_class = SomeOtherContext

        CA1().test()
        CA2().test()

    def test_context_type(self, ca: CAT):
        class CA1(ca, _TestContextType):
            pass

        class CA2(ca, _TestContextType, descent=CA1):
            inherit_context = False

        CA1().test(ca)
        CA2().test(ca)

    def test_descent(self, ca: CAT):
        class CA1(ca):
            pass

        class CA2(CA1):
            def test(self):
                assert self.descent_type is CA1
                assert self.context is CA1.get_context()

        class CA3(CA1, descent=CA2):  # this one's interesting.
            def test(self):
                assert self.descent_type is CA2
                assert self.context is CA1.get_context()

        class CA4(ca, descent=CA1):
            def test(self):
                assert self.descent_type is CA1
                assert self.context is CA2.get_context()

        CA2().test()
        CA3().test()
        CA4().test()

    def test_inherit_context(self, ca: CAT):
        class CA1(ca):
            def test(self):
                assert self.supercontext is None

        class CA2(ca, descent=CA1):
            inherit_context = False

            def test(self):
                assert self.supercontext is CA1.get_context()
                assert self.context is CA2.get_context()

        class CA3(ca, descent=CA1):
            inherit_context = None  # default one

            def test(self):
                assert self.context is CA1.get_context()

        class CA4(ca, descent=CA3):
            inherit_context = False

            def test(self):
                assert self.supercontext is CA3.get_context() is CA1.get_context()
                assert self.context is CA4.get_context()

        class CA5(ca, descent=CA4):
            def test(self):
                CA4.test(self)  # type: ignore

        class CA6(ca, descent=CA5):
            inherit_context = False

            def test(self):
                assert self.supercontext is CA5.get_context()
                assert self.context is CA6.get_context()

        CA1().test()
        CA2().test()
        CA3().test()
        CA4().test()
        CA5().test()
        CA6().test()

    def test_class_dict_arrangement(self):
        from netcast.arrangement import ClassDictArrangement

        class CA1(ClassDictArrangement):
            @classmethod
            def context_wrapper(cls, context):
                for key, default in {'pings': 0, 'pongs': 0}.items():
                    context.setdefault(key, default)
                yield context

            def ping(self):
                self.context.pings += 1

        class CA2(CA1):
            def pong(self):
                self.context.pongs += 1

        ca1 = CA1()
        ca1.ping()
        ca2 = CA2()
        ca2.pong()

        assert CA1.get_context() is CA2.get_context()
        assert ca1.context is ca2.context
        assert ca1.context == {'pings': 1, 'pongs': 1}

        ca1.ping()
        ca2.pong()

        assert ca1.context == {'pings': 2, 'pongs': 2}

        ca2.ping()

        assert ca1.context == {'pings': 3, 'pongs': 2}

    def test_class_list_arrangement(self):
        from netcast.arrangement import ClassListArrangement

        class CA(ClassListArrangement, _TestContextType):
            pass

        CA().test(ClassListArrangement)

        class CA1(ClassListArrangement):
            def one(self):
                self.context.append(1)

        class CA2(CA1):
            def two(self):
                self.context.append(2)

        ca1 = CA1()
        ca1.one()
        ca2 = CA2()
        ca2.two()

        assert ca2.context == [1, 2]

        ca2.one()

        assert ca2.context.pop() == 1
        assert ca2.context == [1, 2]

    def test_class_queue_arrangement(self):
        from netcast.arrangement import ClassQueueArrangement

        class CQA(ClassQueueArrangement):
            get = ForwardDependency()
            put = ForwardDependency()

        class Get(ClassQueueArrangement, descent=CQA):
            def __call__(self):
                self.context.get()

        CQA.get.dependency(Get)

        class Put(ClassQueueArrangement, descent=CQA):
            def __init__(self, *args):
                """We do this to check if ForwardDependency() guessed the unbound param well"""
                assert not args

            def __call__(self, item):
                self.context.put(item)

        CQA.put.dependency(Put)

        qa = CQA()
        assert qa.context is qa.put.context
        assert qa.context is qa.get.context

        qa.put(1)
        assert qa.context.qsize() == 1

        qa.get()
        assert qa.context.qsize() == 0

    @pytest.mark.asyncio
    async def test_class_asyncio_queue_arrangement(self):
        from netcast.arrangement import ClassAsyncioQueueArrangement

        class QueuePut(ClassAsyncioQueueArrangement):
            async def __call__(self, item):
                await self.context.put(item)

        class QueueGet(ClassAsyncioQueueArrangement, descent=QueuePut):
            async def __call__(self):
                return await self.context.get()

        put = QueuePut()
        get = QueueGet()
        queue = put.context

        await asyncio.gather(put(1), put(5), get(), put(3))
        assert queue.qsize() == 2
        await asyncio.gather(get(), put(2), get(), get())
        assert queue.qsize() == 0


class TestArrangement:
    def test_context_type(self, a: AT):
        class A1(a, _TestContextType):
            pass

        class A2(a, _TestContextType, descent=A1):
            inherit_context = False

        a1 = A1()
        a1.test(a)
        # noinspection PyArgumentList
        A2(a1).test(a)

    def test_inherit_context(self, a: AT):
        class A1(a):
            def test(self):
                assert self.supercontext is None
                assert self.inherits_context

        class A2(a, descent=A1):
            def test(self):
                assert self.context is self.descent.context
                assert self.inherits_context

        class A3(a, descent=A2):
            inherit_context = False

            def test(self):
                assert self.supercontext is a1.context
                assert self.supercontext is self.descent.context
                assert self.context is not a1.context
                assert self.context is not self.descent.context
                assert not self.inherits_context

        class A4(a, descent=A3):
            def test(self):
                assert self.supercontext is self.descent.supercontext
                assert self.context is self.descent.context
                assert self.inherits_context

        a1 = A1()
        a2 = A2(a1)
        a3 = A3(a2)
        a4 = A4(a3)
        a1.test()
        a2.test()
        a3.test()
        a4.test()

    def test_dict_arrangement(self):
        from netcast.arrangement import DictArrangement

        class DA1(DictArrangement):
            context_params = Params.from_args(pings=0, pongs=0)

            def clear(self):
                self.context.update(dict.fromkeys(('pings', 'pongs'), 0))

            def ping(self):
                self.context.pings += 1

            def pong(self):
                self.context.pongs += 1

        class DA2(DA1):
            pass

        da1 = DA1()
        da2 = DA2(da1)
        assert da1.context.pings == 0
        assert da2.context.pings == 0
        assert da1.context.pongs == 0
        assert da2.context.pongs == 0

        da2.ping()
        assert da1.context.pings == 1
        assert da1.context.pongs == 0
        assert da2.context.pings == 1
        assert da2.context.pongs == 0

        da1.pong()
        assert da1.context.pings == 1
        assert da1.context.pongs == 1
        assert da2.context.pings == 1
        assert da2.context.pongs == 1

        da1.clear()
        assert da1.context.pings == 0
        assert da2.context.pings == 0
        assert da1.context.pongs == 0
        assert da2.context.pongs == 0

    def test_list_arrangement(self):
        from netcast.arrangement import ListArrangement

        class Appender(ListArrangement):
            def __call__(self, x):
                self.context.append(x)

        class Popper(ListArrangement, descent=Appender):
            def __call__(self, x=-1):
                return self.context.pop(x)

        class Extender(ListArrangement, descent=Appender):
            def __call__(self, x):
                self.context.extend(x)

        append = Appender()
        pop = Popper(append)
        with pytest.raises(TypeError):
            Extender(pop)

        extend = Extender(append)
        unbound = Extender()
        assert unbound.context is not extend.context

        context = append.context
        append(5)
        assert context == [5]
        assert pop() == 5
        assert not context

        extend([1, 2, 3])
        assert context == [1, 2, 3]

        context.clear()
        assert not context

        foreign_appender = Appender()
        assert foreign_appender.context is not context

    def test_string_io_arrangement(self):
        from netcast.arrangement import StringIOArrangement

        class SA(StringIOArrangement):
            read = ForwardDependency()
            write = ForwardDependency()

            def seek(self, offset, whence=0):
                return self.context.seek(offset, whence)

            def tell(self):
                return self.context.tell()

        @SA.read.dependency
        class Reader(StringIOArrangement, descent=SA):
            def __call__(self, nchars=-1):
                return self.context.read(nchars)

        @SA.write.dependency
        class Writer(StringIOArrangement, descent=SA):
            def __call__(self, chars):
                self.context.write(chars)

        sa = SA()

        assert isinstance(sa.read, Reader)
        assert isinstance(sa.write, Writer)
        assert sa.context is sa.read.context
        assert sa.read.context is sa.write.context
        assert sa.read() == ''

        sa.write('hello')
        sa.seek(0)
        content = sa.read()
        assert content == 'hello'

        sa_offset = sa.seek(1)
        assert sa.read() == content[sa_offset:]

    def test_queue_arrangement(self):
        from netcast.arrangement import QueueArrangement

        class QA(QueueArrangement):
            put = ForwardDependency()
            get = ForwardDependency()

        class Put(QueueArrangement, descent=QA):
            def __call__(self, item):
                self.context.put(item)

        QA.put.dependency(Put)

        class Get(QueueArrangement, descent=QA):
            def __call__(self):
                return self.context.get()

        QA.get.dependency(Get)

        qa = QA()
        assert qa.context is qa.put.context
        assert qa.context is qa.get.context

        qa.put(1)
        assert qa.context.qsize() == 1

        qa.get()
        assert qa.context.qsize() == 0

    @pytest.mark.asyncio
    async def test_asyncio_queue_arrangement(self):
        from netcast.arrangement import AsyncioQueueArrangement

        class QueuePut(AsyncioQueueArrangement):
            async def __call__(self, item):
                await self.context.put(item)

        class QueueGet(AsyncioQueueArrangement, descent=QueuePut):
            async def __call__(self):
                return await self.context.get()

        put = QueuePut()
        get = QueueGet(put)
        queue = put.context

        await asyncio.gather(put(1), put(5), get(), put(3))
        assert queue.qsize() == 2
        await asyncio.gather(get(), put(2), get(), get())
        assert queue.qsize() == 0
