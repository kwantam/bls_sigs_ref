#!/usr/bin/python
#
# implementation of Fp and Fp^2 operations
#
# (C) 2018 Chia Network Inc. See copyright notice at end of file.

from copy import deepcopy

p = 0x1a0111ea397fe69a4b1ba7b6434bacd764774b84f38512bf6730d2a0f6b0f6241eabfffeb153ffffb9feffffffffaaab

class Fq(int):
    """
    Represents an element of a finite field mod a prime q.
    """
    Q = None
    extension = 1

    def __new__(cls, Q, x):
        ret = super().__new__(cls, x % Q)
        ret.Q = Q
        return ret

    def __neg__(self):
        return Fq(self.Q, super().__neg__())

    def __add__(self, other):
        if not isinstance(other, int):
            return NotImplemented
        return Fq(self.Q, super().__add__(other))

    def __radd__(self, other):
        if not isinstance(other, int):
            return NotImplemented
        return self.__add__(other)

    def __sub__(self, other):
        if not isinstance(other, int):
            return NotImplemented
        return Fq(self.Q, super().__sub__(other))

    def __rsub__(self, other):
        if not isinstance(other, int):
            return NotImplemented
        return Fq(self.Q, super().__rsub__(other))

    def __mul__(self, other):
        if not isinstance(other, int):
            return NotImplemented
        return Fq(self.Q, super().__mul__(other))

    def __rmul__(self, other):
        return self.__mul__(other)

    def __eq__(self, other):
        if not isinstance(other, type(self)):
            return super().__eq__(other)
        return super().__eq__(other) and self.Q == other.Q

    def __str__(self):
        s = hex(int(self))
        s2 = s[0:7] + ".." + s[-5:] if len(s) > 10 else s
        return "Fq(" + s2 + ")"

    def __repr__(self):
        return "Fq(" + hex(int(self)) + ")"

    def __pow__(self, other):
        if other == 0:
            return Fq(self.Q, 1)
        if other == 1:
            return self
        if other % 2 == 0:
            return (self * self) ** (other // 2)
        return (self * self) ** (other // 2) * self

    def __invert__(self):
        """
        Extended euclidian algorithm for inversion.
        """
        x0, x1, y0, y1 = 1, 0, 0, 1
        a = int(self.Q)
        b = int(self)
        while a != 0:
            q, b, a = b // a, a, b % a
            x0, x1 = x1, x0 - q * x1
            y0, y1 = y1, y0 - q * y1
        return Fq(self.Q, x0)

    def __floordiv__(self, other):
        if (isinstance(other, int) and
                not isinstance(other, type(self))):
            other = Fq(self.Q, other)
        return self * ~other

    __truediv__ = __floordiv__

    def __iter__(self):
        yield self

    def __deepcopy__(self, memo):
        return Fq(self.Q, int(self))

    @classmethod
    def zero(cls, Q):
        return Fq(Q, 0)

    @classmethod
    def one(cls, Q):
        return Fq(Q, 1)

    @classmethod
    def from_fq(cls, _, fq):
        return fq


class FieldExtBase(tuple):
    """
    Represents an extension of a field (or extension of an extension).
    The elements of the tuple can be other FieldExtBase or they can be
    Fq elements. For example, Fq2 = (Fq, Fq). Fq12 = (Fq6, Fq6), etc.
    """
    extension = None
    basefield = None
    embedding = None
    root = None
    Q = None

    def __new__(cls, Q, *args):
        new_args = args[:]
        try:
            arg_extension = args[0].extension
            args[1].extension  # pylint: disable=pointless-statement
        except AttributeError:
            if len(args) != 2:
                raise Exception("Invalid number of arguments")
            arg_extension = 1
            new_args = [Fq(Q, a) for a in args]
        if arg_extension != 1:
            if len(args) != cls.embedding:
                raise Exception("Invalid number of arguments")
            for arg in new_args:
                assert arg.extension == arg_extension
        assert all(isinstance(arg, cls.basefield
                              if cls.basefield is not Fq else int)
                   for arg in new_args)
        ret = super().__new__(cls, new_args)
        ret.Q = Q
        return ret

    def __neg__(self):
        cls = type(self)
        ret = super().__new__(cls, (-x for x in self))
        ret.Q = self.Q
        ret.root = self.root
        return ret

    def __add__(self, other):
        cls = type(self)
        if not isinstance(other, cls):
            if type(other) != int and other.extension > self.extension:  # pylint: disable=unidiomatic-typecheck
                return NotImplemented
            other_new = [cls.basefield.zero(self.Q) for _ in self]
            other_new[0] = other_new[0] + other
        else:
            other_new = other

        ret = super().__new__(cls, (a + b for a, b in zip(self, other_new)))
        ret.Q = self.Q
        ret.root = self.root
        return ret

    def __radd__(self, other):
        return self.__add__(other)

    def __sub__(self, other):
        return self + (-other)

    def __rsub__(self, other):
        return (-self) + other

    def __mul__(self, other):
        cls = type(self)
        if isinstance(other, int):
            ret = super().__new__(cls, (a * other for a in self))
            ret.Q = self.Q
            ret.root = self.root
            return ret
        if cls.extension < other.extension:
            return NotImplemented

        buf = [cls.basefield.zero(self.Q) for _ in self]

        for i, x in enumerate(self):
            if cls.extension == other.extension:
                for j, y in enumerate(other):
                    if x and y:
                        if i+j >= self.embedding:
                            buf[(i + j) % self.embedding] += (x * y *
                                                              self.root)
                        else:
                            buf[(i + j) % self.embedding] += x * y
            else:
                if x:
                    buf[i] = x * other
        ret = super().__new__(cls, buf)
        ret.Q = self.Q
        ret.root = self.root
        return ret

    def __rmul__(self, other):
        return self.__mul__(other)

    def __floordiv__(self, other):
        return self * ~other

    __truediv__ = __floordiv__

    def __eq__(self, other):
        if not isinstance(other, type(self)):
            if isinstance(other, (FieldExtBase, int)):
                if (not isinstance(other, FieldExtBase)
                   or self.extension > other.extension):
                    for i in range(1, self.embedding):
                        if self[i] != (type(self.root).zero(self.Q)):
                            return False
                    return self[0] == other
                return NotImplemented
            return NotImplemented
        return super().__eq__(other) and self.Q == other.Q

    def __lt__(self, other):
        # Reverse the order for comparison (3i + 1 > 2i + 7)
        return self[::-1].__lt__(other[::-1])

    def __neq__(self, other):
        return not self.__eq__(other)

    def __str__(self):
        return ("Fq" + str(self.extension) + "(" + ", ".join([a.__str__()
                                                             for a in self])
                + ")")

    def __repr__(self):
        return ("Fq" + str(self.extension) + "(" + ", ".join([a.__repr__()
                                                             for a in self])
                + ")")

    def __pow__(self, e):
        assert isinstance(e, int) and e >= 0
        ans = type(self).one(self.Q)
        base = self
        ans.root = self.root

        while e:
            if e & 1:
                ans *= base

            base *= base
            e >>= 1

        return ans

    def __bool__(self):
        return any(x for x in self)

    def set_root(self, _root):
        self.root = _root

    @classmethod
    def zero(cls, Q):
        return cls.from_fq(Q, Fq(Q, 0))

    @classmethod
    def one(cls, Q):
        return cls.from_fq(Q, Fq(Q, 1))

    @classmethod
    def from_fq(cls, Q, fq):
        y = cls.basefield.from_fq(Q, fq)
        z = cls.basefield.zero(Q)
        ret = super().__new__(cls,
                              (z if i else y for i in range(cls.embedding)))
        ret.Q = Q
        if cls == Fq2:
            ret.set_root(Fq(Q, -1))
        return ret

    def __deepcopy__(self, memo):
        cls = type(self)
        ret = super().__new__(cls, (deepcopy(a, memo) for a in self))
        ret.Q = self.Q
        ret.root = self.root
        return ret

class Fq2(FieldExtBase):
    # Fq2 is constructed as Fq(u) / (u2 - β) where β = -1
    extension = 2
    embedding = 2
    basefield = Fq

    def __init__(self, Q, *_):
        # pylint: disable=super-init-not-called
        super().set_root(Fq(Q, -1))

    def __invert__(self):
        a, b = self
        factor = ~(a * a + b * b)
        ret = Fq2(self.Q, a * factor, -b * factor)
        return ret

# Copyright 2018 Chia Network Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.