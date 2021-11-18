import construct as cs


def ensure_object(args, kwargs):
    if all((args, kwargs)):
        raise ValueError('args and kwargs are mutually exclusive')
    return args if args else kwargs


class InheritanceLayer:
    def __init__(self, **subcons):
        self.__construct = self.__factory__(**subcons)

    def __call__(self, *args, **kwargs):
        if not hasattr(self, '__subcons__'):
            raise TypeError
        obj = ensure_object(args, kwargs)
        return self.__construct.build(obj)

    def __init_subclass__(cls, _factory=None, _root=False):
        if _root:
            cls.__factory__ = _factory


def heritable(factory):
    return type('heritable_construct', (InheritanceLayer,), {'_factory': factory, '_root': True})


Subconstruct = heritable(cs.Subconstruct)
Compiled = heritable(cs.Compiled)
Bytes = heritable(cs.Bytes)
GreedyBytes = heritable(cs.GreedyBytes)
FormatField = heritable(cs.FormatField)
BytesInteger = heritable(cs.BytesInteger)
BitsInteger = heritable(cs.BitsInteger)
VarInt = heritable(cs.VarInt)
ZigZag = heritable(cs.ZigZag)
Flag = heritable(cs.Flag)
Struct = heritable(cs.Struct)
Sequence = heritable(cs.Sequence)
Computed = heritable(cs.Computed)
Index = heritable(cs.Index)
Check = heritable(cs.Check)
Error = heritable(cs.Error)
FocusedSeq = heritable(cs.FocusedSeq)
Pickled = heritable(cs.Pickled)
Numpy = heritable(cs.Numpy)
Union = heritable(cs.Union)
Select = heritable(cs.Select)
IfThenElse = heritable(cs.IfThenElse)
Switch = heritable(cs.Switch)
StopIf = heritable(cs.StopIf)
Seek = heritable(cs.Seek)
Tell = heritable(cs.Tell)
Pass = heritable(cs.Pass)
Terminated = heritable(cs.Terminated)
Checksum = heritable(cs.Checksum)
LazyStruct = heritable(cs.LazyStruct)
LazyBound = heritable(cs.LazyBound)
Probe = heritable(cs.Probe)
