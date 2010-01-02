import os
import tempfile
import unittest
import sys

from nose.tools import \
    assert_equal

try:
    from cStringIO import StringIO
finally:
    from StringIO import StringIO

from toydist.core.pkg_objects import \
    DataFiles, Executable

class TestDataFiles(unittest.TestCase):
    def test_simple(self):
        data = DataFiles("data", files=["foo.c"])
        assert_equal(data.name, "data")
        assert_equal(data.files, ["foo.c"])
        assert_equal(data.srcdir, ".")
        assert_equal(data.target, "$sitedir")

    def test_from_dict(self):
        parsed_dict = {"files": "foo.c, yo.c", "target": "foo"}
        data = DataFiles.from_parse_dict("data", parsed_dict)
        assert_equal(data.name, "data")
        assert_equal(data.files, ["foo.c", "yo.c"])
        assert_equal(data.target, "foo")
    # TODO: test with a populated temp dir

class TestExecutable(unittest.TestCase):
    def test_basic(self):
        exe = Executable.from_representation("foo=core:main")
        assert_equal(exe.name, "foo")
        assert_equal(exe.module, "core")
        assert_equal(exe.function, "main")

        assert_equal(exe.full_representation(), "foo=core:main")
