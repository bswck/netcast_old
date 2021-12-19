from netcast.arrangement import ClassArrangement, Arrangement, ListArrangement
from netcast.context import ListContext


class CA1(ClassArrangement):
    def __init__(self):
        self.context.hello = 1
        self.ca2 = CA2()
        assert self.context.get('hello_again')


class CA2(ClassArrangement, descent=CA1):
    def __init__(self):
        if self.context.get('hello') == 1:
            self.context.hello_again = 1


ca1 = CA1()
ca2 = ca1.ca2
assert ca1.context == ca2.context


class CA3(ClassArrangement, descent=CA2):
    inherit_context = False

    def __init__(self):
        self.supercontext.hello_cas = 1
        self.context.helloed = 1


ca3 = CA3()
assert ca1.context.get('hello_cas')
assert ca3.context.get('helloed')


class A1(Arrangement):
    def __init__(self):
        super().__init__()
        self.a2 = A2(self)


class A2(Arrangement, descent=A1):
    pass


class A3(Arrangement, descent=A1):
    inherit_context = False


a1 = A1()
a1.context.update(a=1)
a2 = a1.a2
assert a2.descent is a1
assert a1.context is a2.context
a3 = A3(a1)
assert a1.context is not a3.context
assert a1.context is a3.supercontext


class LA1(ListArrangement):
    def __init__(self):
        self.context.append(0)
        self.la2 = LA2(self)
        self.la2.append_1()
        self.la3 = LA3(self.la2)
        self.la3.append_top(5)
        self.la3.append(1)


class LA2(ListArrangement, descent=LA1):
    def append_1(self):
        self.context.append(1)


class LA3(ListArrangement, descent=LA2):
    inherit_context = False

    def append(self, x):
        self.context.append(x)

    def append_top(self, x):
        self.supercontext.append(x)


la1 = LA1()
la2 = la1.la2
la3 = la1.la3
assert la1.context.__class__ == ListContext
assert la1.context == [0, 1, 5]
assert la1.context is la2.context is la3.supercontext
assert la3.context == [1]

