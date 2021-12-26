from typing import ClassVar

import pytest

from netcast.arrangement import DEFAULT_CONTEXT_CLASS, AT, CAT
from netcast.arrangement import ClassArrangement, Arrangement
from netcast.context import C, CT

ca_params = {ClassArrangement, *ClassArrangement.__subclasses__()} - {Arrangement}


@pytest.fixture(params=ca_params)
def ca(request) -> CAT:
    yield request.param


a_params = {Arrangement, *Arrangement.__subclasses__()}


@pytest.fixture(params=a_params)
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
            def test(self):
                assert isinstance(self.context, Abstract.context_class)  # we want a list here

        class CA2(Abstract):
            def test(self):
                assert isinstance(self.context, Abstract.context_class)  # we want a list here

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

    def test_class_deque_arrangement(self):
        pass

    def test_class_queue_arrangement(self):
        pass

    def test_class_lifo_queue_arrangement(self):
        pass

    def test_class_priority_queue_arrangement(self):
        pass

    def test_class_asyncio_queue_arrangement(self):
        pass

    def test_class_asyncio_lifo_queue_arrangement(self):
        pass

    def test_class_asyncio_priority_queue_arrangement(self):
        pass


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

        class A1(DictArrangement):
            pass

    def test_list_arrangement(self):
        pass

    def test_deque_arrangement(self):
        pass

    def test_queue_arrangement(self):
        pass

    def test_lifo_queue_arrangement(self):
        pass

    def test_priority_queue_arrangement(self):
        pass

    def test_asyncio_queue_arrangement(self):
        pass

    def test_asyncio_lifo_queue_arrangement(self):
        pass

    def test_asyncio_priority_queue_arrangement(self):
        pass
