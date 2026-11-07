from pathlib import Path
import importlib.util
import struct
import tempfile
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('public_bps', ROOT / 'patches/R1/bps.py')
bps = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bps)


def number(n):
    result = bytearray()
    while True:
        value = n & 127
        n >>= 7
        if not n:
            return result + bytes([value | 128])
        result.append(value)
        n -= 1


def fixture(source, target, actions):
    raw = b'BPS1' + number(len(source)) + number(len(target)) + number(0) + actions
    raw += struct.pack('<II', zlib.crc32(source), zlib.crc32(target))
    return raw + struct.pack('<I', zlib.crc32(raw))


class BpsContracts(unittest.TestCase):
    def test_independent_source_read_fixture(self):
        source = b'ABCD'
        patch = fixture(source, source, number((4 - 1) << 2))
        self.assertEqual(bps.decode(patch, source), source)

    def test_independent_overlapping_target_copy_fixture(self):
        target = b'abcabcabc'
        actions = number(((3 - 1) << 2) | 1) + b'abc' + number(((6 - 1) << 2) | 3) + number(0)
        self.assertEqual(bps.decode(fixture(b'', target, actions), b''), target)

    def test_independent_signed_source_copy_fixture(self):
        source = b'0123456789'
        actions = number(((3 - 1) << 2) | 2) + number(10)
        actions += number(((2 - 1) << 2) | 2) + number(15)
        self.assertEqual(bps.decode(fixture(source, b'56712', actions), source), b'56712')

    def test_corrupt_and_truncated_patch_rejected(self):
        source = b'abc'
        patch = fixture(source, source, number((3 - 1) << 2))
        for broken in [patch[:-1], b'X' + patch[1:], patch[:-5] + bytes([patch[-5] ^ 1]) + patch[-4:]]:
            with self.assertRaises((ValueError, AssertionError, IndexError)):
                bps.decode(broken, source)

    def test_wrong_source_rejected(self):
        patch = fixture(b'abc', b'abc', number((3 - 1) << 2))
        with self.assertRaises((ValueError, AssertionError)):
            bps.decode(patch, b'abd')

    def test_out_of_bounds_source_copy_rejected(self):
        patch = fixture(b'abc', b'ab', number(((2 - 1) << 2) | 2) + number(200))
        with self.assertRaises((ValueError, AssertionError)):
            bps.decode(patch, b'abc')


if __name__ == '__main__':
    unittest.main()
