import shutil
import os

from toydist.utils import \
    subst_vars
from toydist.cabal_parser.cabal_parser import \
    ParseError

META_DELIM = "!- FILELIST"
FIELD_DELIM = ("\t", " ")

class InstalledPkgDescription(object):
    def __init__(self, files, path_options):
        self.files = files
        self._path_variables = path_options

        self._path_variables['_srcrootdir'] = "."

    def write(self, filename):
        fid = open(filename, "w")
        try:
            path_fields = "\n".join([
                "\t%s=%s" % (name, value) for name, value in
                                              self._path_variables.items()])

            path_section = """\
paths
%s
%s
""" % (path_fields, META_DELIM)
            fid.write(path_section)

            for name, value in self.files.items():
                if name in ["pythonfiles"]:
                    source = "$_srcrootdir"
                    target = value["target"]
                    files = value["files"]
                    fid.write(write_file_section(name, source, target, files))
                elif name in ["datafiles"]:
                    for dname, dvalue in self.files["datafiles"].items():
                        source = dvalue["source"]
                        target = dvalue["target"]
                        files = dvalue["files"]
                        fid.write(write_file_section(dname, source, target, files))
                elif name in ["extensions"]:
                    for ename, evalue in self.files["extensions"].items():
                        source = evalue["source"]
                        target = evalue["target"]
                        files = evalue["files"]
                        fid.write(write_file_section("extension", source, target, files))
                else:
                    raise ValueError("Unknown section %s" % name)

        finally:
            fid.close()

def write_file_section(name, source, target, files):
    section = """\
%(section)s
%(source)s
%(target)s
%(files)s
""" % {"section": name,
       "source": "\tsource=%s" % source,
       "target": "\ttarget=%s" % target,
       "files": "\n".join(["\t%s" % f for f in files])}
    return section

def read_installed_pkg_description(filename):
    f = open(filename)
    try:
        meta = []
        r = Reader(f.readlines())
        while r.wait_for("!- FILELIST\n"):
            meta.append(r.pop())
        if r.eof():
            r.parse_error("Missing filelist section")
        r.pop()

        if not meta[0].strip() == "paths":
            raise ValueError("no path ?")

        path_vars = {}
        for i in meta[1:]:
            name, value = [j.strip() for j in i.split("=")]
            path_vars[name] = value

        def read_section():
            r.flush_empty()
            line = r.peek()
            if line and line[0] in FIELD_DELIM:
                r.parse_error("No section found ?")
            line = r.pop()
            section_name = line.strip()

            source = r.pop().strip()
            target = r.pop().strip()
            assert source.startswith("source=")
            assert target.startswith("target=")
            source = source.split("=")[1]
            target = target.split("=")[1]

            source = subst_vars(source, path_vars)
            target = subst_vars(target, path_vars)

            files = []
            line = r.peek()
            while line and line[0] in FIELD_DELIM:
                file = r.pop().strip()
                files.append((os.path.join(source, file), os.path.join(target, file)))
                line = r.peek()

            return section_name, files

        file_sections = {}
        while not r.eof():
            name, files = read_section()
            file_sections[name] = files
        return file_sections
    finally:
        f.close()

# XXX: abstract this with the reader in cabal_parser
class Reader(object):
    def __init__(self, data):
        self._data = data
        self._idx = 0

    def flush_empty(self):
        """Read until a non-empty line is found."""
        while not (self.eof() or self._data[self._idx].strip()):
            self._idx += 1

    def pop(self, blank=False):
        """Return the next non-empty line and increment the line
        counter.  If `blank` is True, then also return blank lines.

        """
        if not blank:
            # Skip to the next non-empty line if blank is not set
            self.flush_empty()

        line = self.peek(blank)
        self._idx += 1

        return line

    def peek(self, blank=False):
        """Return the next non-empty line without incrementing the
        line counter.  If `blank` is True, also return blank lines.

        Peek is not allowed to touch _idx.

        """
        if self.eof():
            return ''

        save_idx = self._idx
        if not blank:
            self.flush_empty()

        peek_line = self._data[self._idx]
        self._idx = save_idx

        return peek_line

    def eof(self):
        """Return True if the end of the file has been reached."""
        return self._idx >= len(self._data)

    @property
    def index(self):
        """Return the line-counter to the pre-processed version of
        the input file.

        """
        return self._idx

    @property
    def line(self):
        """Return the line-counter to the original input file.

        """
        lines = 0
        for l in self._data[:self._idx]:
            if not l in ['{', '}']:
                lines += 1
        return lines

    def wait_for(self, line):
        """Keep reading until the given line has been seen."""
        if self.eof():
            return False
        elif self.peek() != line:
            return True
        else:
            return False

    def parse_error(self, msg):
        """Raise a parsing error with the given message."""
        raise ParseError('''

Parsing error at line %s (%s):
%s
Parser traceback: %s''' %
                         (self.line, msg, self._original_data[self.line],
                          ' -> '.join(self._traceback)))

