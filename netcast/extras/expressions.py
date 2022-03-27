# flake8: noqa
from __future__ import annotations  # Python 3.8

import enum
import math
import operator
from typing import Any, Callable, Union, Literal

from netcast.constants import MISSING
from netcast.tools import strings
from netcast.tools.collections import ParameterHolder

__all__ = (
    "EvalFlags",
    "Variable",
    "variable",
    "variables",
    "Expression",
    "ExpressionOps",
)


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
        if (flags & cls.PRE_DUMP_REVERSE) and (flags & cls.POST_LOAD_REVERSE):
            mutex_flags.append("PRE_DUMP_REVERSE and POST_LOAD_REVERSE")

        if mutex_flags:
            raise ValueError(ambiguity_msg % ", ".join(mutex_flags))
        return flags


PRE = PRE_DUMP = EvalFlags.PRE_DUMP
PREREVERSE = PRE_DUMP_REVERSE = EvalFlags.PRE_DUMP_REVERSE
POST = POST_LOAD = EvalFlags.POST_LOAD
POSTREVERSE = POST_LOAD_REVERSE = EvalFlags.POST_LOAD_REVERSE


class ExpressionOps:
    def _operative(self):
        return self

    def __add__(self, other):
        return Add(self._operative(), other)

    def __radd__(self, other):
        return Add(other, self._operative())

    def concat(self, other):
        return Concatenate(self._operative(), other)

    with_suffix = concat

    def concat_left(self, other):
        return ConcatenateLeft(self._operative(), other)

    with_prefix = concat_left

    def __sub__(self, other):
        return Subtract(self._operative(), other)

    def __rsub__(self, other):
        return Subtract(other, self._operative())

    def __mul__(self, other):
        return Multiply(self._operative(), other)

    def __rmul__(self, other):
        return Multiply(other, self._operative())

    def __truediv__(self, other):
        return Divide(self._operative(), other)

    def __rtruediv__(self, other):
        return Divide(other, self._operative())

    def __floordiv__(self, other):
        return FloorDivide(self._operative(), other)

    def __rfloordiv__(self, other):
        return FloorDivide(other, self._operative())

    def __pow__(self, other):
        return Power(self._operative(), other)

    def __rpow__(self, other):
        return Power(other, self._operative())

    def root(self, other):
        return Root(self._operative(), other)

    def __mod__(self, other):
        return Modulo(self._operative(), other)

    def __rmod__(self, other):
        return Modulo(other, self._operative())

    def divmod(self, other):
        return DivMod(self._operative(), other)

    def __lshift__(self, other):
        return ShiftLeft(self._operative(), other)

    def __rlshift__(self, other):
        return ShiftLeft(other, self._operative())

    def __rshift__(self, other):
        return ShiftRight(self._operative(), other)

    def __rrshift__(self, other):
        return ShiftRight(other, self._operative())

    def __and__(self, other):
        return AND(self._operative(), other)

    def __rand__(self, other):
        return AND(other, self._operative())

    def nand(self, other):
        return NAND(self._operative(), other)

    def __or__(self, other):
        return OR(self._operative(), other)

    def __ror__(self, other):
        return OR(other, self._operative())

    def nor(self, other):
        return NOR(self._operative(), other)

    def __xor__(self, other):
        return XOR(self._operative(), other)

    def __rxor__(self, other):
        return XOR(other, self._operative())

    def equ(self, other):
        return EQU(self._operative(), other)

    def and_(self, other):
        return And(self._operative(), other)

    def nand_(self, other):
        return NAnd(self._operative(), other)

    def or_(self, other):
        return Or(self._operative(), other)

    def nor_(self, other):
        return NOr(self._operative(), other)

    def xor_(self, other):
        return XOr(self._operative(), other)

    def __eq__(self, other):
        return Equal(self._operative(), other)

    def getitem(self, other):
        return GetItem(self._operative(), other)

    get = getitem

    def getattr(self, other):
        return GetAttr(self._operative(), other)

    def call(self, other):
        return Call(self._operative(), other)

    def called_by(self, other):
        return Call(other, self._operative())

    def __invert__(self):
        return self.called_by(operator.not_)

    def __pos__(self):
        return self.called_by(operator.pos)

    def __neg__(self):
        return self.called_by(operator.neg)

    def is_(self, other):
        return Is(self._operative(), other)

    def is_not(self, other):
        return IsNot(self._operative(), other)

    def in_(self, other):
        return Contains(other, self._operative())

    def __contains__(self, other):
        return Contains(self._operative(), other)

    @property
    def math(self):
        return MathOps(self)


class OpsExtension(ExpressionOps):
    def __init__(self, wrapped):
        self.wrapped = wrapped

    def _operative(self):
        return self.wrapped


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
        for key in kwargs.keys() & configurable_keys:
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
        return (procedure == PRE and self.flags & PREREVERSE) or (
            procedure == POST and self.flags & POSTREVERSE
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
            raise ValueError(
                "value processor was not declared (and thus is not callable)"
            )
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
        return f"{type(self).__name__}({self.left}, {self.right})".lstrip("~")


_DelegateT = Union[Callable[[Any, Any], Any], Callable[[Expression, Any, Any], Any]]


def _left(left, _):
    return left


def _reverse_pow(left, right):
    return left ** (1 / right)


def _ireverse_pow(left, right):
    left **= 1 / right
    return left


def _reverse_divmod(left, right):
    n, remainder = left
    return n * right + remainder


def _nand(left, right):
    return ~(left & right)


def _nor(left, right):
    return ~(left | right)


def _concat_left(left, right):
    if not hasattr(right, "__getitem__"):
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


class Is(Expression):
    irreversible = True
    op_func = staticmethod(operator.is_)


class IsNot(Expression):
    irreversible = True
    op_func = staticmethod(operator.is_not)


class Contains(Expression):
    irreversible = True
    op_func = staticmethod(operator.contains)


class Call(Expression):
    irreversible = True

    def op_func(self, left, right):
        if isinstance(right, ParameterHolder):
            return left(*right.eval_arguments(left), **right.eval_keywords(left))
        return left(right)


class MathOps(OpsExtension):
    class ATan2(Expression):
        irreversible = True
        op_func = staticmethod(math.atan2)

    class Comb(Expression):
        irreversible = True
        op_func = staticmethod(math.comb)

    class CopySign(Expression):
        irreversible = True
        op_func = staticmethod(math.copysign)

    class Dist(Expression):
        irreversible = True
        op_func = staticmethod(math.dist)

    class FMod(Expression):
        irreversible = True
        op_func = staticmethod(math.fmod)

    class GCD(Expression):
        irreversible = True
        op_func = staticmethod(math.gcd)

    class IsClose(Expression):
        def __init__(self, *args, **kwargs):
            self.rel_tol = kwargs.pop("rel_tol", 1e-09)
            self.abs_tol = kwargs.pop("abs_tol", 0.0)
            super().__init__(*args, **kwargs)

        irreversible = True
        op_func = staticmethod(math.isclose)

    class LDExp(Expression):
        op_func = staticmethod(math.ldexp)
        opreverse_func = staticmethod(lambda left, right: left / (2**right))

    class Log(Expression):
        irreversible = True
        op_func = staticmethod(math.log)

    class Perm(Expression):
        irreversible = True
        op_func = staticmethod(math.perm)

    class Pow(Expression):
        irreversible = True
        op_func = staticmethod(math.pow)

    class Prod(Expression):
        irreversible = True
        op_func = staticmethod(math.prod)

    class Remainder(Expression):
        irreversible = True
        op_func = staticmethod(math.remainder)

    def acos(self):
        return self.called_by(math.acos)

    def acosh(self):
        return self.called_by(math.acosh)

    def asin(self):
        return self.called_by(math.asin)

    def asinh(self):
        return self.called_by(math.asinh)

    def atan(self):
        return self.called_by(math.atan)

    def atan2(self, other):
        return self.ATan2(self._operative(), other)

    def atanh(self):
        return self.called_by(math.atanh)

    def ceil(self):
        return self.called_by(math.ceil)

    def comb(self, other):
        return self.Comb(self._operative(), other)

    def copysign(self, other):
        return self.CopySign(self._operative(), other)

    def cos(self):
        return self.called_by(math.cos)

    def cosh(self):
        return self.called_by(math.cosh)

    def degrees(self):
        return self.called_by(math.degrees)

    def dist(self, other):
        return self.Dist(self._operative(), other)

    def erf(self):
        return self.called_by(math.erf)

    def erfc(self):
        return self.called_by(math.erfc)

    def exp(self):
        return self.called_by(math.exp)

    def expm1(self):
        return self.called_by(math.expm1)

    def fabs(self):
        return self.called_by(math.fabs)

    def factorial(self):
        return self.called_by(math.factorial)

    def floor(self):
        return self.called_by(math.floor)

    def fmod(self, other):
        return self.FMod(self._operative(), other)

    def frexp(self):
        return self.called_by(math.frexp)

    def fsum(self):
        return self.called_by(math.fsum)

    def gamma(self):
        return self.called_by(math.gamma)

    def gcd(self, other):
        return self.GCD(self._operative(), other)

    def hypot(self):
        return self.called_by(math.hypot)

    def isclose(self, other, rel_tol=1e-09, abs_tol=0.0):
        return self.IsClose(self._operative(), other, rel_tol=rel_tol, abs_tol=abs_tol)

    def isfinite(self):
        return self.called_by(math.isfinite)

    def isinf(self):
        return self.called_by(math.isinf)

    def isnan(self):
        return self.called_by(math.isnan)

    def isqrt(self):
        return self.called_by(math.isqrt)

    def ldexp(self, other):
        return self.LDExp(self._operative(), other)

    def lgamma(self):
        return self.called_by(math.lgamma)

    def log(self, base=None):
        return self.Log(self._operative(), base)

    def log10(self):
        return self.called_by(math.log10)

    def log1p(self):
        return self.called_by(math.log1p)

    def log2(self):
        return self.called_by(math.log2)

    def modf(self):
        return self.called_by(math.modf)

    def perm(self, other):
        return self.Perm(self._operative(), other)

    def pow(self, other):
        return self.Pow(self._operative(), other)

    def prod(self, start=1):
        return self.Prod(self._operative(), start)

    def radians(self):
        return self.called_by(math.radians)

    def remainder(self, other):
        return self.Remainder(self._operative(), other)

    def sin(self):
        return self.called_by(math.sin)

    def sinh(self):
        return self.called_by(math.sinh)

    def sqrt(self):
        return self.called_by(math.sqrt)

    def tan(self):
        return self.called_by(math.tan)

    def tanh(self):
        return self.called_by(math.tanh)

    def trunc(self):
        return self.called_by(math.trunc)
