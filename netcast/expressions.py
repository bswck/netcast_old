from __future__ import annotations  # Python 3.8

import enum
import operator
from typing import Any, Callable, Union, Literal, TYPE_CHECKING

from netcast.constants import MISSING
from netcast.tools import strings

try:
    # noinspection PyUnresolvedReferences
    import numpy
except ImportError:
    NUMPY = False
else:
    NUMPY = True

if TYPE_CHECKING:
    from netcast.tools.symbol import Symbol


class EvaluationFlags(enum.IntFlag):
    PRE_DUMP = 1 << 0
    PRE_DUMP_RECOVER = 1 << 1
    POST_LOAD = 1 << 2
    POST_LOAD_RECOVER = 1 << 3

    @classmethod
    def validate(cls, flags: int | EvaluationFlags):
        mutex_msg = "mutually exclusive listed execution flags flags: %s"
        mutex_flags = []

        if (flags & cls.PRE_DUMP) and (flags & cls.PRE_DUMP_RECOVER):
            mutex_flags.append("PRE_DUMP and PRE_DUMP_RECOVER")

        if (flags & cls.POST_LOAD) and (flags & cls.POST_LOAD_RECOVER):
            mutex_flags.append("POST_LOAD and POST_LOAD_RECOVER")

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
                (flags & cls.PRE_DUMP_RECOVER)
                and (flags & cls.POST_LOAD_RECOVER)
        ):
            mutex_flags.append("PRE_DUMP_RECOVER and POST_LOAD_RECOVER")

        if mutex_flags:
            raise ValueError(ambiguity_msg % ", ".join(mutex_flags))


PRE = PRE_DUMP = EvaluationFlags.PRE_DUMP
PRERECOV = PRE_DUMP_RECOVER = EvaluationFlags.PRE_DUMP_RECOVER
POST = POST_LOAD = EvaluationFlags.POST_LOAD
POSTRECOV = POST_LOAD_RECOVER = EvaluationFlags.POST_LOAD_RECOVER


class ExpressionOpsMeta(type):
    def __add__(cls, other): return Add(cls, other)
    def __radd__(cls, other): return Add(other, cls)
    def concat(cls, other): return Concatenate(cls, other)
    with_suffix = concat
    def concat_left(cls, other): return ConcatenateLeft(cls, other)
    with_prefix = concat_left
    def __sub__(cls, other): return Subtract(cls, other)
    def __rsub__(cls, other): return Subtract(other, cls)
    def __mul__(cls, other): return Multiply(cls, other)
    def __rmul__(cls, other): return Multiply(other, cls)
    def __truediv__(cls, other): return Divide(cls, other)
    def __rtruediv__(cls, other): return Divide(other, cls)
    def __floordiv__(cls, other): return FloorDivide(cls, other)
    def __rfloordiv__(cls, other): return FloorDivide(other, cls)
    def __pow__(cls, other): return Power(cls, other)
    def __rpow__(cls, other): return Power(other, cls)
    def root(cls, other): return Root(cls, other)
    def __mod__(cls, other): return Modulo(cls, other)
    def __rmod__(cls, other): return Modulo(other, cls)
    def divmod(cls, other): return DivMod(cls, other)
    def __lshift__(cls, other): return ShiftLeft(cls, other)
    def __rlshift__(cls, other): return ShiftLeft(other, cls)
    def __rshift__(cls, other): return ShiftRight(cls, other)
    def __rrshift__(cls, other): return ShiftLeft(other, cls)
    def __and__(cls, other): return AND(cls, other)
    def __rand__(cls, other): return AND(other, cls)
    def nand(cls, other): return NAND(cls, other)
    def __or__(cls, other): return OR(cls, other)
    def __ror__(cls, other): return OR(other, cls)
    def nor(cls, other): return NOR(cls, other)
    def __xor__(cls, other): return XOR(cls, other)
    def __rxor__(cls, other): return XOR(other, cls)
    def equ(cls, other): return EQU(cls, other)
    def and_(cls, other): return And(cls, other)
    def nand_(cls, other): return NAnd(cls, other)
    def or_(cls, other): return Or(cls, other)
    def nor_(cls, other): return NOr(cls, other)
    def xor_(cls, other): return XOr(cls, other)
    def __eq__(cls, other): return Equal(cls, other)
    def getitem(cls, other): return GetItem(cls, other)
    get = getitem
    def getattr(cls, other): return GetAttr(cls, other)
    def call(cls, other): return Call(cls, other)
    def called_by(cls, other): return Call(other, cls)


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
    def __rrshift__(self, other): return ShiftLeft(other, self)
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
    opback_func: _DelegateT
    iopback_func: _DelegateT

    _require_left = True

    def __init__(
            self,
            left: Any | Expression = MISSING,
            right: Any | Expression = MISSING,
            *,
            const: bool = False,
            flags: int = PRE | POSTRECOV,
            inplace: bool = False,
            back: bool = False,
            _back_right: bool = True,
            _back_kwargs: dict[str, Any] | None = None
    ):
        if self._require_left and left is MISSING:
            raise ValueError("missing required value to create an expression")

        if back:
            if _back_kwargs is None:
                _back_kwargs = {}
            self.parse_kwargs(**_back_kwargs)
            if isinstance(left, Expression):
                left = self._back_node(left, _back_kwargs)
            if _back_right and isinstance(right, Expression):
                right = self._back_node(right, _back_kwargs)

        self.left = left
        self.right = right
        self.const = const
        self.flags = flags
        EvaluationFlags.validate(flags)
        self.inplace = inplace
        self.__back = back

    def configure(self, **kwargs):
        configurable = {"const", "flags"}
        for key in (kwargs.keys() & configurable):
            new_value = kwargs.get(key, MISSING)
            if new_value is not MISSING:
                setattr(self, key, new_value)

    def parse_kwargs(self, **kwargs):
        pass

    def eval(self, procedure: Literal[PRE, POST] = PRE, **kwargs):
        if procedure in (PRERECOV, POSTRECOV):
            raise ValueError("back flags are invalid in this context")
        self.parse_kwargs(**kwargs)
        return self._eval(procedure, **kwargs)

    def _eval(self, procedure, **kwargs) -> Any:
        if self.__back:
            processor = self._get_processor("opback_func")
        else:
            processor = self._get_processor("op_func")
        if not callable(processor):
            raise ValueError("value processor was not declared (and thus is not callable)")
        left, right = self._resolve_operands(procedure, **kwargs)
        return processor(left, right)

    def _resolve_operands(self, procedure, **kwargs):
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

    def back(self, _back_right=True, _back_kwargs=None):
        back = type(self)(
            left=self.left,
            right=self.right,
            const=self.const,
            flags=self.flags,
            inplace=self.inplace,
            back=True,
            _back_right=_back_right,
            _back_kwargs=_back_kwargs
        )
        return back

    @staticmethod
    def _back_node(node, kwargs=None):
        if kwargs is None:
            kwargs = {}
        node.parse_kwargs(**kwargs)
        if isinstance(node, Variable):
            node = node.back(node.name, _back_right=True, **kwargs)
        else:
            node = node.back(_back_kwargs=kwargs)
        return node

    def __repr__(self):
        return ("", "^")[self.__back] + (
            f"{type(self).__name__}({self.left}, {self.right})".lstrip("~")
        )

_DelegateT = Union[Callable[[Any, Any], Any], Callable[[Expression, Any, Any], Any]]


def _left(left, _):
    return left


def _back_pow(left, right):
    return left ** (1 / right)


def _iback_pow(left, right):
    left **= (1 / right)
    return left


def _back_divmod(left, right):
    n, remainder = left
    return n * right + remainder


def _nand(left, right):
    return ~(left & right)


def _nor(left, right):
    return ~(left | right)


class Variable(Expression):
    op_func = opback_func = staticmethod(_left)
    _require_left = False

    def __init__(self, *args, **kwargs):
        self._back = MISSING
        name = kwargs.pop("name", None)
        if name is None:
            raise ValueError("variable must be identified with a name")
        self.name = name
        if "right" in kwargs:
            raise ValueError("variable takes only the left value")
        if kwargs.get("back"):
            self._require_left = True
        super().__init__(*args, **kwargs)

    def set(self, expr):
        self.left = expr

    def parse_kwargs(self, **kwargs):
        self.left = kwargs.get(self.name, self.left)
        if self.left is MISSING:
            raise ValueError(f"variable {self.name} was not set but requested usage")

    def back(self, name: str = "y", focus: str | Symbol = MISSING, _back_right=False, **kwargs):
        if self._back is MISSING:
            left = self.left
            if isinstance(left, Expression):
                left = left.back(_back_right=_back_right, _back_kwargs=kwargs)
            self._back = type(self)(left, name=name)
        return self._back

    def __repr__(self):
        return self.name + "=" + repr(self.left)


class Add(Expression):
    """Addition expression."""
    op_func = staticmethod(operator.add)
    iop_func = staticmethod(operator.iadd)
    opback_func = staticmethod(operator.sub)
    iopback_func = staticmethod(operator.isub)


class Concatenate(Expression):
    """Concatenation expression."""
    op_func = staticmethod(operator.concat)
    iop_func = staticmethod(operator.iconcat)
    opback_func = staticmethod(strings.remove_suffix)


class ConcatenateLeft(Expression):
    """Left concatenation expression."""
    op_func = staticmethod(operator.concat)
    iop_func = staticmethod(operator.iconcat)
    opback_func = staticmethod(strings.remove_prefix)


class Subtract(Expression):
    """Subtraction expression."""
    op_func = staticmethod(operator.sub)
    iop_func = staticmethod(operator.isub)
    opback_func = staticmethod(operator.add)
    iopback_func = staticmethod(operator.iadd)


class Multiply(Expression):
    """Multiplication expression."""
    op_func = staticmethod(operator.mul)
    iop_func = staticmethod(operator.imul)
    opback_func = staticmethod(operator.truediv)
    iopback_func = staticmethod(operator.itruediv)


class Divide(Expression):
    """Division expression."""
    op_func = staticmethod(operator.truediv)
    iop_func = staticmethod(operator.itruediv)
    opback_func = staticmethod(operator.mul)
    iopback_func = staticmethod(operator.imul)


class FloorDivide(Expression):
    """Floor division expression."""
    op_func = staticmethod(operator.floordiv)
    iop_func = staticmethod(operator.ifloordiv)
    opback_func = staticmethod(operator.mul)
    iopback_func = staticmethod(operator.imul)


class Power(Expression):
    """Exponentiation expression."""
    op_func = staticmethod(operator.pow)
    iop_func = staticmethod(operator.pow)
    opback_func = staticmethod(_back_pow)
    iopback_func = staticmethod(_iback_pow)


class Root(Expression):
    """Root expression."""
    op_func = staticmethod(_back_pow)
    iop_func = staticmethod(_iback_pow)
    opback_func = staticmethod(operator.pow)
    iopback_func = staticmethod(operator.pow)


class Modulo(Expression):
    """Division and modulo expression."""
    op_func = staticmethod(operator.mod)
    iop_func = staticmethod(operator.imod)
    opback_func = staticmethod(_left)


class DivMod(Expression):
    """Division and modulo expression."""
    op_func = staticmethod(divmod)
    opback_func = staticmethod(_back_divmod)


class MatrixMultiply(Expression):
    """Matrix multiplication (a @ b) expression."""
    op_func = staticmethod(operator.rshift)
    iop_func = staticmethod(operator.irshift)


class ShiftLeft(Expression):
    """Shift left (a << b) expression."""
    op_func = staticmethod(operator.lshift)
    iop_func = staticmethod(operator.ilshift)
    opback_func = staticmethod(operator.rshift)
    iopback_func = staticmethod(operator.irshift)


class ShiftRight(Expression):
    """Shift right (a >> b) expression."""
    op_func = staticmethod(operator.rshift)
    iop_func = staticmethod(operator.irshift)
    opback_func = staticmethod(operator.lshift)
    iopback_func = staticmethod(operator.ilshift)


class AND(Expression):
    """Bitwise AND (a & b) expression."""
    op_func = staticmethod(operator.and_)
    iop_func = staticmethod(operator.iand)
    opback_func = staticmethod(_left)


class NAND(Expression):
    """Bitwise NAND (~(a & b)) expression."""
    op_func = staticmethod(_nand)
    opback_func = staticmethod(_left)


class OR(Expression):
    """Bitwise OR (a | b) expression."""
    op_func = staticmethod(operator.or_)
    iop_func = staticmethod(operator.ior)
    opback_func = staticmethod(_left)


class NOR(Expression):
    """Bitwise NOR (~(a | b)) expression."""
    op_func = staticmethod(_nor)
    opback_func = staticmethod(_left)


class XOR(Expression):
    """Bitwise XOR (a ^ b) expression."""
    op_func = staticmethod(operator.xor)
    iop_func = staticmethod(operator.ixor)
    opback_func = staticmethod(_left)


class EQU(Expression):
    """Bitwise EQU (~(a ^ b)) expression."""
    op_func = staticmethod(operator.xor)
    iop_func = staticmethod(operator.ixor)
    opback_func = staticmethod(_left)


class And(Expression):
    """Logical AND (a and b) expression."""
    op_func = staticmethod(lambda left, right: left and right)
    opback_func = staticmethod(_left)


class NAnd(Expression):
    """Logical NAND (not (a and right)) expression."""
    op_func = staticmethod(lambda left, right: (left, right)[(left and right) is left])
    opback_func = staticmethod(_left)


class Or(Expression):
    """Logical OR (a or right) expression."""
    op_func = staticmethod(lambda left, right: left or right)
    opback_func = staticmethod(_left)


class NOr(Expression):
    """Logical NOR (not (a or right)) expression."""
    op_func = staticmethod(lambda left, right: (left, right)[(left or right) is left])
    opback_func = staticmethod(_left)


class XOr(Expression):
    """Logical XOR (a ^ right) expression."""
    op_func = staticmethod(lambda left, right: bool(left) ^ bool(right))
    opback_func = staticmethod(_left)


class Equal(Expression):
    """Logical EQU (a == right) expression."""
    op_func = staticmethod(lambda left, right: left == right)
    opback_func = staticmethod(_left)


class GetItem(Expression):
    op_func = staticmethod(lambda left, right: left[right])
    opback_func = staticmethod(_left)


class GetAttr(Expression):
    op_func = staticmethod(getattr)
    opback_func = staticmethod(_left)


class Call(Expression):
    op_func = staticmethod(lambda left, right: (
        left(*right.args, **right.kwargs)
        if hasattr(right, "args") and hasattr(right, "kwargs")
        else left(right)
    ))
    opback_func = staticmethod(_left)
