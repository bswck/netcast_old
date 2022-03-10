from __future__ import annotations  # Python 3.8

import enum
import operator
from typing import Any, Callable, Union, Literal

from netcast.constants import MISSING
from netcast.tools import strings


class EvalFlags(enum.IntFlag):
    PRE_DUMP = 1 << 0
    PRE_DUMP_REVERSE = 1 << 1
    POST_LOAD = 1 << 2
    POST_LOAD_REVERSE = 1 << 3

    @classmethod
    def validate(cls, flags: int | EvalFlags):
        mutex_msg = "mutually exclusive listed execution flags: %s"
        mutex_flags = []

        flags &= 0b1111

        if (flags & cls.PRE_DUMP) and (flags & cls.PRE_DUMP_REVERSE):
            mutex_flags.append("PRE_DUMP and PRE_DUMP_REVERSE")

        if (flags & cls.POST_LOAD) and (flags & cls.POST_LOAD_REVERSE):
            mutex_flags.append("POST_LOAD and POST_LOAD_REVERSE")

        if mutex_flags:
            raise ValueError(mutex_msg % ", ".join(mutex_flags))

        ambiguity_msg = (
            "%s execution flags "
            "double the expression evaluation in a common direction which is ambiguous "
            "and unsupported; expression redesign or checking for mistakes is recommended"
        )

        if (flags & cls.PRE_DUMP) and (flags & cls.POST_LOAD):
            mutex_flags.append("PRE_DUMP and POST_LOAD")
        if (
                (flags & cls.PRE_DUMP_REVERSE)
                and (flags & cls.POST_LOAD_REVERSE)
        ):
            mutex_flags.append("PRE_DUMP_REVERSE and POST_LOAD_REVERSE")

        if mutex_flags:
            raise ValueError(ambiguity_msg % ", ".join(mutex_flags))
        return flags


PRE = PRE_DUMP = EvalFlags.PRE_DUMP
PREREVERSE = PRE_DUMP_REVERSE = EvalFlags.PRE_DUMP_REVERSE
POST = POST_LOAD = EvalFlags.POST_LOAD
POSTREVERSE = POST_LOAD_REVERSE = EvalFlags.POST_LOAD_REVERSE


class ExpressionOps:
    def __add__(self, other): return Add(self, other)
    def __radd__(self, other): return Add(other, self)
    def concat(self, other): return Concatenate(self, other)
    with_suffix = concat
    def concat_left(self, other): return ConcatenateLeft(self, other)
    with_prefix = concat_left
    def __sub__(self, other): return Subtract(self, other)
    def __rsub__(self, other): return Subtract(other, self)
    def __mul__(self, other): return Multiply(self, other)
    def __rmul__(self, other): return Multiply(other, self)
    def __truediv__(self, other): return Divide(self, other)
    def __rtruediv__(self, other): return Divide(other, self)
    def __floordiv__(self, other): return FloorDivide(self, other)
    def __rfloordiv__(self, other): return FloorDivide(other, self)
    def __pow__(self, other): return Power(self, other)
    def __rpow__(self, other): return Power(other, self)
    def root(self, other): return Root(self, other)
    def __mod__(self, other): return Modulo(self, other)
    def __rmod__(self, other): return Modulo(other, self)
    def divmod(self, other): return DivMod(self, other)
    def __lshift__(self, other): return ShiftLeft(self, other)
    def __rlshift__(self, other): return ShiftLeft(other, self)
    def __rshift__(self, other): return ShiftRight(self, other)
    def __rrshift__(self, other): return ShiftRight(other, self)
    def __and__(self, other): return AND(self, other)
    def __rand__(self, other): return AND(other, self)
    def nand(self, other): return NAND(self, other)
    def __or__(self, other): return OR(self, other)
    def __ror__(self, other): return OR(other, self)
    def nor(self, other): return NOR(self, other)
    def __xor__(self, other): return XOR(self, other)
    def __rxor__(self, other): return XOR(other, self)
    def equ(self, other): return EQU(self, other)
    def and_(self, other): return And(self, other)
    def nand_(self, other): return NAnd(self, other)
    def or_(self, other): return Or(self, other)
    def nor_(self, other): return NOr(self, other)
    def xor_(self, other): return XOr(self, other)
    def __eq__(self, other): return Equal(self, other)
    def getitem(self, other): return GetItem(self, other)
    get = getitem
    def getattr(self, other): return GetAttr(self, other)
    def call(self, other): return Call(self, other)
    def called_by(self, other): return Call(other, self)


class Expression(ExpressionOps):
    """
    Expressions that declare various pre-serialization and post-deserialization operations
    to automate processing.
    """
    op_func: _DelegateT
    iop_func: _DelegateT
    opreverse_func: _DelegateT
    iopreverse_func: _DelegateT

    irreversible = False
    _require_left = True

    def __init__(
            self,
            left: Any | Expression = MISSING,
            right: Any | Expression = MISSING,
            *,
            const: bool = False,
            flags: int = PRE | POSTREVERSE,
            inplace: bool = False,
    ):
        if self._require_left and left is MISSING:
            raise ValueError("missing required value to create an expression")

        self.left = left
        self.right = right
        self.const = const
        self.flags = EvalFlags.validate(flags)
        self.inplace = inplace
        self.__cache = MISSING

    def conf(self, **kwargs):
        configurable_keys = {"const", "flags"}
        for key in (kwargs.keys() & configurable_keys):
            new_value = kwargs.get(key, MISSING)
            if key == "flags":
                new_value = EvalFlags.validate(new_value)
            if new_value is not MISSING:
                setattr(self, key, new_value)
        return self

    def parametrize(self, **kwargs):
        pass

    def eval(self, procedure: Literal[PRE, POST] = PRE, **params):
        if self.__cache is not MISSING:
            return self.__cache
        if procedure in (PREREVERSE, POSTREVERSE):
            raise ValueError("reverse flags are invalid in this context")
        self.parametrize(**params)
        result = self._eval(procedure, **params)
        if self.const:
            self.__cache = result
        return result

    def is_reversed(self, procedure):
        return (
            (procedure == PRE and self.flags & PREREVERSE)
            or (procedure == POST and self.flags & POSTREVERSE)
        )

    def _eval(self, procedure, **kwargs) -> Any:
        if self.is_reversed(procedure):
            if self.irreversible:
                processor = _left
            else:
                processor = self._get_processor("opreverse_func")
                if processor is None:
                    raise NotImplementedError(
                        "cannot reverse an expression that is marked reversible. "
                        "Consider using `irreversible = True` setting"
                    )
        else:
            processor = self._get_processor("op_func")
        if not callable(processor):
            raise ValueError("value processor was not declared (and thus is not callable)")
        left, right = self._eval_branches(procedure, **kwargs)
        return processor(left, right)

    def _eval_branches(self, procedure, **kwargs):
        operands = []
        for node_name in ("left", "right"):
            operand = node = getattr(self, node_name)
            if isinstance(node, Expression):
                operand = node.eval(procedure, **kwargs)
                if node.const:
                    setattr(self, node_name, operand)
            operands.append(operand)
        return operands

    def _get_processor(self, attr_name) -> Callable:
        iattr_name = ("i" if self.inplace else "") + attr_name
        fallback = getattr(self, attr_name) if self.inplace else None
        return getattr(self, iattr_name, fallback)

    def __repr__(self):
        return (
            f"{type(self).__name__}({self.left}, {self.right})".lstrip("~")
        )

_DelegateT = Union[Callable[[Any, Any], Any], Callable[[Expression, Any, Any], Any]]


def _left(left, _):
    return left


def _reverse_pow(left, right):
    return left ** (1 / right)


def _ireverse_pow(left, right):
    left **= (1 / right)
    return left


def _reverse_divmod(left, right):
    n, remainder = left
    return n * right + remainder


def _nand(left, right):
    return ~(left & right)


def _nor(left, right):
    return ~(left | right)


def _concat_left(left, right):
    if not hasattr(right, '__getitem__'):
        msg = "%r object can't be concatenated" % type(right).__name__
        raise TypeError(msg)
    return right + left


class Variable(Expression):
    _require_left = False
    op_func = staticmethod(_left)

    def __init__(self, *args, **kwargs):
        name = kwargs.pop("name", None)
        if name is None:
            raise ValueError("variable must be identified with a name")
        self.name = name
        if kwargs.get("reverse"):
            self._require_left = True
        super().__init__(*args, **kwargs)
        if self.right is not MISSING:
            raise ValueError("variable takes only the left value")

    def set(self, expr):
        self.left = expr

    def clear(self):
        self.left = MISSING

    @property
    def value(self):
        return self.left

    value.setter(set)

    def parametrize(self, **kwargs):
        self.left = kwargs.get(self.name, self.left)
        if self.left is MISSING:
            raise ValueError(f"variable {self.name} was not set but requested usage")

    def __repr__(self):
        return self.name + ("" if self.left is MISSING else ("=" + repr(self.left)))


def variable(name, init=MISSING):
    return Variable(init, name=name)


def variables(names):
    variable_names = names.replace(",", " ").split()
    return map(variable, variable_names)


class Add(Expression):
    """Addition expression."""
    op_func = staticmethod(operator.add)
    iop_func = staticmethod(operator.iadd)
    opreverse_func = staticmethod(operator.sub)
    iopreverse_func = staticmethod(operator.isub)


class Concatenate(Expression):
    """Concatenation expression."""
    op_func = staticmethod(operator.concat)
    iop_func = staticmethod(operator.iconcat)
    opreverse_func = staticmethod(strings.remove_suffix)


class ConcatenateLeft(Expression):
    """Left concatenation expression."""
    op_func = staticmethod(_concat_left)
    opreverse_func = staticmethod(strings.remove_prefix)


class Subtract(Expression):
    """Subtraction expression."""
    op_func = staticmethod(operator.sub)
    iop_func = staticmethod(operator.isub)
    opreverse_func = staticmethod(operator.add)
    iopreverse_func = staticmethod(operator.iadd)


class Multiply(Expression):
    """Multiplication expression."""
    op_func = staticmethod(operator.mul)
    iop_func = staticmethod(operator.imul)
    opreverse_func = staticmethod(operator.truediv)
    iopreverse_func = staticmethod(operator.itruediv)


class Divide(Expression):
    """Division expression."""
    op_func = staticmethod(operator.truediv)
    iop_func = staticmethod(operator.itruediv)
    opreverse_func = staticmethod(operator.mul)
    iopreverse_func = staticmethod(operator.imul)


class FloorDivide(Expression):
    """Floor division expression."""
    op_func = staticmethod(operator.floordiv)
    iop_func = staticmethod(operator.ifloordiv)
    opreverse_func = staticmethod(operator.mul)
    iopreverse_func = staticmethod(operator.imul)


class Power(Expression):
    """Exponentiation expression."""
    op_func = staticmethod(operator.pow)
    iop_func = staticmethod(operator.pow)
    opreverse_func = staticmethod(_reverse_pow)
    iopreverse_func = staticmethod(_ireverse_pow)


class Root(Expression):
    """Root expression."""
    op_func = staticmethod(_reverse_pow)
    iop_func = staticmethod(_ireverse_pow)
    opreverse_func = staticmethod(operator.pow)
    iopreverse_func = staticmethod(operator.pow)


class Modulo(Expression):
    """Division and modulo expression."""
    irreversible = True
    op_func = staticmethod(operator.mod)
    iop_func = staticmethod(operator.imod)


class DivMod(Expression):
    """Division and modulo expression."""
    op_func = staticmethod(divmod)
    opreverse_func = staticmethod(_reverse_divmod)


class MatrixMultiply(Expression):
    """Matrix multiplication (a @ b) expression."""
    op_func = staticmethod(operator.rshift)
    iop_func = staticmethod(operator.irshift)


class ShiftLeft(Expression):
    """Shift left (a << b) expression."""
    op_func = staticmethod(operator.lshift)
    iop_func = staticmethod(operator.ilshift)
    opreverse_func = staticmethod(operator.rshift)
    iopreverse_func = staticmethod(operator.irshift)


class ShiftRight(Expression):
    """Shift right (a >> b) expression."""
    op_func = staticmethod(operator.rshift)
    iop_func = staticmethod(operator.irshift)
    opreverse_func = staticmethod(operator.lshift)
    iopreverse_func = staticmethod(operator.ilshift)


class AND(Expression):
    """Bitwise AND (a & b) expression."""
    irreversible = True
    op_func = staticmethod(operator.and_)
    iop_func = staticmethod(operator.iand)


class NAND(Expression):
    """Bitwise NAND (~(a & b)) expression."""
    irreversible = True
    op_func = staticmethod(_nand)


class OR(Expression):
    """Bitwise OR (a | b) expression."""
    irreversible = True
    op_func = staticmethod(operator.or_)
    iop_func = staticmethod(operator.ior)


class NOR(Expression):
    """Bitwise NOR (~(a | b)) expression."""
    irreversible = True
    op_func = staticmethod(_nor)


class XOR(Expression):
    """Bitwise XOR (a ^ b) expression."""
    irreversible = True
    op_func = staticmethod(operator.xor)
    iop_func = staticmethod(operator.ixor)


class EQU(Expression):
    """Bitwise EQU (~(a ^ b)) expression."""
    irreversible = True
    op_func = staticmethod(lambda left, right: ~(left ^ right))


class And(Expression):
    """Logical AND (a and b) expression."""
    irreversible = True
    op_func = staticmethod(lambda left, right: left and right)


class NAnd(Expression):
    """Logical NAND (not (a and right)) expression."""
    irreversible = True
    op_func = staticmethod(lambda left, right: (left, right)[(left and right) is left])


class Or(Expression):
    """Logical OR (a or right) expression."""
    op_func = staticmethod(lambda left, right: left or right)
    irreversible = True


class NOr(Expression):
    """Logical NOR (not (a or right)) expression."""
    irreversible = True
    op_func = staticmethod(lambda left, right: (left, right)[(left or right) is left])


class XOr(Expression):
    """Logical XOR (a ^ right) expression."""
    irreversible = True
    op_func = staticmethod(lambda left, right: bool(left) ^ bool(right))


class Equal(Expression):
    """Logical EQU (a == right) expression."""
    op_func = staticmethod(lambda left, right: left == right)
    irreversible = True


class GetItem(Expression):
    irreversible = True
    op_func = staticmethod(lambda left, right: left[right])


class GetAttr(Expression):
    irreversible = True
    op_func = staticmethod(getattr)


class Call(Expression):
    irreversible = True
    op_func = staticmethod(lambda left, right: (
        left(*right.args, **right.kwargs)
        if hasattr(right, "args") and hasattr(right, "kwargs")
        else left(right)
    ))
