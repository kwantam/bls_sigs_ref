#!/usr/bin/env sage
# vim: syntax=python
#
# point serialization / deserialization
# using the "enhanced ZCash" format proposed in
#     https://github.com/pairingwg/bls_standard/issues/16
# (C) 2019 Riad S. Wahby <rsw@cs.stanford.edu>

import struct
import sys

try:
    from __sage__g1_common import Ell, F, ZZR, p, sgn0
    from __sage__g2_common import Ell2, F2, X, sqrt_F2
except ImportError:
    sys.exit("Error loading preprocessed sage files. Try running `make clean pyfiles`")

def serialize(P, compressed=True):
    if P.curve() == Ell:
        return _serialize_ell1(P, compressed)
    if P.curve() == Ell2:
        return _serialize_ell2(P, compressed)
    raise ValueError("cannot serialize a point not on E1 or E2")

def to_bytes_F1(elm):
    if elm.parent() != F:
        raise ValueError("value must be an element of F1")
    val = int(elm)
    ret = [0] * 48
    for idx in reversed(xrange(0, 48)):
        ret[idx] = val & 0xff
        val = val >> 8
    return ret

def _serialize_ell1(P, compressed):
    if P.curve() != Ell:
        raise ValueError("cannot serialize a point not on E1")

    # handle point at infinity
    if P.is_zero():
        if compressed:
            return "\xc0" + "\x00" * 47
        return "\x40" + "\x00" * 95

    x_str = to_bytes_F1(P[0])
    if not compressed:
        return struct.pack("=" + "B" * 96, *(x_str + to_bytes_F1(P[1])))

    y_neg = sgn0(P[1]) < 0
    tag_bits = 0xa0 if y_neg else 0x80
    x_str[0] = x_str[0] | tag_bits
    return struct.pack("=" + "B" * 48, *x_str)

def to_bytes_F2(elm):
    if elm.parent() != F2:
        raise ValueError("value must be an element of F2")
    zzelm = ZZR(elm)
    return to_bytes_F1(F(zzelm[1])) + to_bytes_F1(F(zzelm[0]))

def _serialize_ell2(P, compressed):
    if P.curve() != Ell2:
        raise ValueError("cannot serialize a point not on E2")

    first_tag = 0xe0 if compressed else 0x60

    # handle point at infinity
    if P.is_zero():
        ret = chr(first_tag) + "\x00" * 47 + "\xc0" + "\x00" * 47
        if not compressed:
            ret += "\x00" * 96
        return ret

    x_str = to_bytes_F2(P[0])
    x_str[0] = x_str[0] | first_tag
    if not compressed:
        x_str[48] = x_str[48] | 0x80
        return struct.pack("=" + "B" * 192, *(x_str + to_bytes_F2(P[1])))

    y_neg = sgn0(P[1]) < 0
    tag_bits = 0xa0 if y_neg else 0x80
    x_str[48] = x_str[48] | tag_bits
    return struct.pack("=" + "B" * 96, *x_str)

def deserialize(sp):
    data = list(struct.unpack("=" + "B" * len(sp), sp))
    (tag, data[0]) = (data[0] >> 5, data[0] & 0x1f)
    if tag == 1:
        raise ValueError("invalid tag '1'")
    if tag in (3, 7):
        return _deserialize_ell2(data, tag)
    return _deserialize_ell1(data, tag)

def from_bytes_F1(data):
    assert len(data) == 48
    ret = 0
    for d in data:
        ret = ret << 8
        ret += d
    if ret >= p:
        raise ValueError("invalid encoded value: not a residue mod p")
    return F(ret)

def _deserialize_ell1(data, tag):
    if tag == 0:
        # uncompressed point
        if len(data) != 96:
            raise ValueError("invalid uncompressed point: length must be 96, got %d" % len(data))
        x = from_bytes_F1(data[:48])
        y = from_bytes_F1(data[48:])
        return Ell(x, y)

    if tag in (2, 6):
        # point at infinity
        expected_len = 96 if tag == 2 else 48
        if len(data) != expected_len:
            raise ValueError("invalid point at infinity: length must be %d, got %d" % (expected_len, len(data)))
        if any( d != 0 for d in data ):
            raise ValueError("invalid: point at infinity must be all 0s other than tag")
        return Ell(0, 1, 0)

    if tag in (4, 5):
        # compressed point not at infinity
        if len(data) != 48:
            raise ValueError("invalid compressed point: length must be 48, got %d" % len(data))
        x = from_bytes_F1(data)

        # recompute y
        gx = x ** 3 + F(4)
        y = gx ** ((p + 1) // 4)
        if y ** 2 != gx:
            raise ValueError("invalid compressed point: g(x) is nonsquare")

        # fix sign of y
        y_neg = -1 if tag == 5 else 1
        y = y_neg * sgn0(y) * y

        return Ell(x, y)

    raise ValueError("invalid tag for Ell1 point: %d" % tag)

def from_bytes_F2(data):
    assert len(data) == 96
    return F2(X * from_bytes_F1(data[:48]) + from_bytes_F1(data[48:]))

def _deserialize_ell2(data, tag):
    assert len(data) > 48
    (tag2, data[48]) = (data[48] >> 5, data[48] & 0x1f)
    if tag2 not in (4, 5, 6):
        raise ValueError("invalid tag2 for Ell2 point: %d" % tag2)

    if tag2 == 6:
        # point at infinity
        expected_len = 192 if tag == 3 else 96
        if len(data) != expected_len:
            raise ValueError("invalid point at infinity: length must be %d, got %d" % (expected_len, len(data)))
        if any( d != 0 for d in data ):
            raise ValueError("invalid: point at infinity must be all 0s other than tags")
        return Ell2(0, 1, 0)

    if tag == 3:
        # uncompressed point on G2
        if len(data) != 192:
            raise ValueError("invalid uncompressed point: length must be 192, got %d" % len(data))
        if tag2 == 5:
            raise ValueError("invalid uncompressed point: tag2 cannot be 5")
        x = from_bytes_F2(data[:96])
        y = from_bytes_F2(data[96:])
        return Ell2(x, y)

    if tag == 7:
        # compressed point on G2
        if len(data) != 96:
            raise ValueError("invalid compressed point: length must be 96, got %d" % len(data))
        x = from_bytes_F2(data)

        # recompute y
        gx = x ** 3 + 4 * (X + 1)
        y = sqrt_F2(gx)
        if y is None:
            raise ValueError("invalid compressed point: g(x) is nonsquare")

        # fix sign of y
        y_neg = -1 if tag2 == 5 else 1
        y = y_neg * sgn0(y) * y

        return Ell2(x, y)

    raise ValueError("invalid tag for Ell2 point: %d" % (tag, tag2))

if __name__ == "__main__":
    def test_ell(P=None, ell2=False):
        P = (Ell2 if ell2 else Ell).random_point() if P is None else P
        Puc = deserialize(serialize(P, False))
        Pc = deserialize(serialize(P, True))
        assert P == Puc, "%s\n%s\n%d %d" % (str(P), str(Puc), sgn0(P[1]), sgn0(Puc[1]))
        assert P == Pc, "%s\n%s\n%d %d" % (str(P), str(Pc), sgn0(P[1]), sgn0(Pc[1]))
    test_ell(Ell(0, 1, 0), False)
    test_ell(Ell(0, 1, 0), True)
    test_ell(Ell2(0, 1, 0), False)
    test_ell(Ell2(0, 1, 0), True)
    for i in range(0, 32):
        sys.stdout.write('.')
        sys.stdout.flush()
        test_ell(None, False)
        test_ell(None, True)
    print
    # TODO(rsw): add tests for invalid serializations, too!