"""
Classes for querying the information in a test coverage report.
"""

import itertools
import os
import os.path
import re
from collections import defaultdict

from diff_cover import util
from diff_cover.command_runner import run_command_for_code
from diff_cover.git_path import GitPathTool
from diff_cover.violationsreporters.base import (
    BaseViolationReporter,
    QualityDriver,
    RegexBasedDriver,
    Violation,
)


class XmlCoverageReporter(BaseViolationReporter):
    """
    Query information from a Cobertura|Clover|JaCoCo XML coverage report.
    """

    def __init__(self, xml_roots, src_roots=None, expand_coverage_report=False):
        """
        Load the XML coverage report represented
        by the cElementTree with root element `xml_root`.
        """
        super().__init__("XML")
        self._xml_roots = xml_roots

        # Create a dict to cache violations dict results
        # Keys are source file paths, values are output of `violations()`
        self._info_cache = defaultdict(list)

        # Create a list to cache xml classes list results
        # Values are output of `self._get_xml_classes()`
        self._xml_cache = [{} for i in range(len(xml_roots))]

        self._src_roots = src_roots or [""]
        self._expand_coverage_report = expand_coverage_report

    def _get_xml_classes(self, xml_document):
        """
        Return a dict of classes in `xml_document`.
        Keys are `filename`, values are list of `class`

        If `class` is not present in `xml_document`,
        return empty defaultdict(list)
        """
        # cobertura sometimes provides the sources for the measurements
        # within it. If we have that we outta use it
        sources = xml_document.findall("sources/source")
        sources = [source.text for source in sources if source.text]
        classes = xml_document.findall(".//class") or []

        res = defaultdict(list)
        for clazz in classes:
            f = clazz.get("filename")
            if not f:
                continue
            res[util.to_unix_path(f)].append(clazz)
            for source in sources:
                abs_f = util.to_unix_path(os.path.join(source.strip(), f))
                res[abs_f].append(clazz)
        return res

    def _get_classes(self, index, xml_document, src_path):
        """
        Given a path and parsed xml_document provides class nodes
        with the relevant lines

        First, we look to see if xml_document contains a source
        node providing paths to search for

        If we don't have that we check each nodes filename attribute
        matches an absolute path

        Finally, if we found no nodes, we check the filename attribute
        for the relative path
        """
        # Remove git_root from src_path for searching the correct filename
        # If cwd is `/home/user/work/diff-cover/diff_cover`
        # and src_path is `diff_cover/violations_reporter.py`
        # search for `violations_reporter.py`
        src_rel_path = util.to_unix_path(GitPathTool.relative_path(src_path))

        # If cwd is `/home/user/work/diff-cover/diff_cover`
        # and src_path is `other_package/some_file.py`
        # search for `/home/user/work/diff-cover/other_package/some_file.py`
        src_abs_path = util.to_unix_path(GitPathTool.absolute_path(src_path))

        # Create a cache for `classes` in `xml_document` if cache exists
        if not self._xml_cache[index]:
            self._xml_cache[index] = self._get_xml_classes(xml_document)

        return self._xml_cache[index].get(src_abs_path) or self._xml_cache[index].get(
            src_rel_path
        )

    def get_src_path_line_nodes_cobertura(self, index, xml_document, src_path):
        classes = self._get_classes(index, xml_document, src_path)

        if not classes:
            return None
        lines = [clazz.findall("./lines/line") for clazz in classes]
        return list(itertools.chain(*lines))

    @staticmethod
    def get_src_path_line_nodes_clover(xml_document, src_path):
        """
        Return a list of nodes containing line information for `src_path`
        in `xml_document`.

        If file is not present in `xml_document`, return None
        """

        files = [
            file_tree
            for file_tree in xml_document.findall(".//file")
            if GitPathTool.relative_path(file_tree.get("path")) == src_path
        ]
        if not files:
            return None
        lines = []
        for file_tree in files:
            lines.append(file_tree.findall('./line[@type="stmt"]'))
            lines.append(file_tree.findall('./line[@type="cond"]'))
        return list(itertools.chain(*lines))

    def _measured_source_path_matches(self, package_name, file_name, src_path):
        # find src_path in any of the source roots
        if not src_path.endswith(file_name):
            return False

        norm_src_path = os.path.normcase(src_path)
        for root in self._src_roots:
            if (
                os.path.normcase(
                    GitPathTool.relative_path(
                        os.path.join(root, package_name, file_name)
                    )
                )
                == norm_src_path
            ):
                return True
        return False

    def get_src_path_line_nodes_jacoco(self, xml_document, src_path):
        """
        Return a list of nodes containing line information for `src_path`
        in `xml_document`.

        If file is not present in `xml_document`, return None
        """

        files = []
        packages = list(xml_document.findall(".//package"))
        for pkg in packages:
            _files = [
                _file
                for _file in pkg.findall("sourcefile")
                if self._measured_source_path_matches(
                    pkg.get("name"), _file.get("name"), src_path
                )
            ]
            files.extend(_files)

        if not files:
            return None
        lines = [file_tree.findall("./line") for file_tree in files]
        return list(itertools.chain(*lines))

    def _cache_file(self, src_path):
        """
        Load the data from `self._xml_roots`
        for `src_path`, if it hasn't been already.
        """
        # If we have not yet loaded this source file
        if src_path not in self._info_cache:
            # We only want to keep violations that show up in each xml source.
            # Thus, each time, we take the intersection.  However, to do this
            # we must treat the first time as a special case and just add all
            # the violations from the first xml report.
            violations = None

            # A line is measured if it is measured in any of the reports, so
            # we take set union each time and can just start with the empty set
            measured = set()

            # Loop through the files that contain the xml roots
            for i, xml_document in enumerate(self._xml_roots):
                if xml_document.findall(".[@clover]"):
                    # see etc/schema/clover.xsd at  https://bitbucket.org/atlassian/clover/src
                    line_nodes = self.get_src_path_line_nodes_clover(
                        xml_document, src_path
                    )
                    _number = "num"
                    _hits = "count"
                elif xml_document.findall(".[@name]"):
                    # https://github.com/jacoco/jacoco/blob/master/org.jacoco.report/src/org/jacoco/report/xml/report.dtd
                    line_nodes = self.get_src_path_line_nodes_jacoco(
                        xml_document, src_path
                    )
                    _number = "nr"
                    _hits = "ci"
                else:
                    # https://github.com/cobertura/web/blob/master/htdocs/xml/coverage-04.dtd
                    line_nodes = self.get_src_path_line_nodes_cobertura(
                        i, xml_document, src_path
                    )
                    _number = "number"
                    _hits = "hits"
                if line_nodes is None:
                    continue

                # Expand coverage report with not reported lines
                if self._expand_coverage_report:
                    reported_line_hits = {}
                    for line in line_nodes:
                        reported_line_hits[int(line.get(_number))] = int(
                            line.get(_hits, 0)
                        )
                    if reported_line_hits:
                        last_hit_number = 0
                        for line_number in range(
                            min(reported_line_hits.keys()),
                            max(reported_line_hits.keys()),
                        ):
                            if line_number in reported_line_hits:
                                last_hit_number = reported_line_hits[line_number]
                            else:
                                # This is an unreported line.
                                # We add it with the previous line hit score
                                line_nodes.append(
                                    {_hits: last_hit_number, _number: line_number}
                                )

                # First case, need to define violations initially
                if violations is None:
                    violations = {
                        Violation(int(line.get(_number)), None)
                        for line in line_nodes
                        if int(line.get(_hits, 0)) == 0
                    }

                # If we already have a violations set,
                # take the intersection of the new
                # violations set and its old self
                else:
                    violations = violations & {
                        Violation(int(line.get(_number)), None)
                        for line in line_nodes
                        if int(line.get(_hits, 0)) == 0
                    }

                # Measured is the union of itself and the new measured
                measured = measured | {int(line.get(_number)) for line in line_nodes}

            # If we don't have any information about the source file,
            # don't report any violations
            if violations is None:
                violations = set()

            self._info_cache[src_path] = (violations, measured)

    def violations(self, src_path):
        """
        See base class comments.
        """

        self._cache_file(src_path)

        # Yield all lines not covered
        return self._info_cache[src_path][0]

    def measured_lines(self, src_path):
        """
        See base class docstring.
        """
        self._cache_file(src_path)
        return self._info_cache[src_path][1]


class LcovCoverageReporter(BaseViolationReporter):
    """
    Query information from a LCov coverage report.
    """

    def __init__(self, lcov_roots, src_roots=None):
        """
        Load the lcov.info coverage report represented
        """
        super().__init__("LCOV")
        self._lcov_roots = lcov_roots
        self._lcov_report = defaultdict(list)

        # Create a dict to cache violations dict results
        # Keys are source file paths, values are output of `violations()`
        self._info_cache = defaultdict(list)

        self._src_roots = src_roots or [""]

    @staticmethod
    def parse(lcov_file):
        """
        Parse a single LCov coverage report
        File format: https://ltp.sourceforge.net/coverage/lcov/geninfo.1.php
        """
        lcov_report = defaultdict(dict)
        lcov = open(lcov_file)
        while True:
            line = lcov.readline()
            if not line:
                break
            directive, _, content = line.strip().partition(":")
            # we're only interested in file name and line coverage
            if directive == "SF":
                # SF:<absolute path to the source file>
                source_file = util.to_unix_path(GitPathTool.relative_path(content))
                continue
            elif directive == "DA":
                # DA:<line number>,<execution count>[,<checksum>]
                args = content.split(",")
                if len(args) < 2 or len(args) > 3:
                    raise ValueError(f"Unknown syntax in lcov report: {line}")
                line_no = int(args[0])
                num_executions = int(args[1])
                if source_file is None:
                    raise ValueError(
                        f"No source file specified for line coverage: {line}"
                    )
                if line_no not in lcov_report[source_file]:
                    lcov_report[source_file][line_no] = 0
                lcov_report[source_file][line_no] += num_executions
            elif directive in [
                "TN",
                "FNF",
                "FNH",
                "FN",
                "FNDA",
                "LH",
                "LF",
                "BRF",
                "BRH",
                "BRDA",
                "VER",
            ]:
                # these are valid lines, but not we don't need them
                continue
            elif directive == "end_of_record":
                source_file = None
            else:
                raise ValueError(f"Unknown syntax in lcov report: {line}")

        lcov.close()
        return lcov_report

    def _cache_file(self, src_path):
        """
        Load the data from `self._lcov_roots`
        for `src_path`, if it hasn't been already.
        """
        # If we have not yet loaded this source file
        if src_path not in self._info_cache:
            # We only want to keep violations that show up in each xml source.
            # Thus, each time, we take the intersection.  However, to do this
            # we must treat the first time as a special case and just add all
            # the violations from the first xml report.
            violations = None

            # A line is measured if it is measured in any of the reports, so
            # we take set union each time and can just start with the empty set
            measured = set()

            # Remove git_root from src_path for searching the correct filename
            # If cwd is `/home/user/work/diff-cover/diff_cover`
            # and src_path is `diff_cover/violations_reporter.py`
            # search for `violations_reporter.py`
            src_rel_path = util.to_unix_path(GitPathTool.relative_path(src_path))

            # If cwd is `/home/user/work/diff-cover/diff_cover`
            # and src_path is `other_package/some_file.py`
            # search for `/home/user/work/diff-cover/other_package/some_file.py`
            src_abs_path = util.to_unix_path(GitPathTool.absolute_path(src_path))

            # Loop through the files that contain the xml roots
            for lcov_document in self._lcov_roots:
                src_search_path = src_abs_path
                if src_search_path not in lcov_document:
                    src_search_path = src_rel_path

                # First case, need to define violations initially
                if violations is None:
                    violations = {
                        Violation(int(line_no), None)
                        for line_no, num_executions in lcov_document[
                            src_search_path
                        ].items()
                        if int(num_executions) == 0
                    }

                # If we already have a violations set,
                # take the intersection of the new
                # violations set and its old self
                else:
                    violations = violations & {
                        Violation(int(line_no), None)
                        for line_no, num_executions in lcov_document[
                            src_search_path
                        ].items()
                        if int(num_executions) == 0
                    }

                # Measured is the union of itself and the new measured
                # measured = measured | {int(line.get(_number)) for line in line_nodes}
                measured = measured | {
                    int(line_no)
                    for line_no, num_executions in lcov_document[
                        src_search_path
                    ].items()
                }

            # If we don't have any information about the source file,
            # don't report any violations
            if violations is None:
                violations = set()

            self._info_cache[src_path] = (violations, measured)

    def violations(self, src_path):
        """
        See base class comments.
        """

        self._cache_file(src_path)

        # Yield all lines not covered
        return self._info_cache[src_path][0]

    def measured_lines(self, src_path):
        """
        See base class docstring.
        """
        self._cache_file(src_path)
        return self._info_cache[src_path][1]


pycodestyle_driver = RegexBasedDriver(
    name="pycodestyle",
    supported_extensions=["py"],
    command=["pycodestyle"],
    expression=r"^([^:]+):(\d+).*([EW]\d{3}.*)$",
    command_to_check_install=["pycodestyle", "--version"],
    # pycodestyle exit code is 1 if there are violations
    # http://pycodestyle.pycqa.org/en/latest/intro.html
    exit_codes=[0, 1],
)

pyflakes_driver = RegexBasedDriver(
    name="pyflakes",
    supported_extensions=["py"],
    command=["pyflakes"],
    # Match lines of the form:
    # path/to/file.py:328: undefined name '_thing'
    # path/to/file.py:418: 'random' imported but unused
    expression=r"^([^:]+):(\d+):\d*:? (.*)$",
    command_to_check_install=["pyflakes", "--version"],
    # pyflakes exit code is 1 if there are violations
    # https://github.com/PyCQA/pyflakes/blob/master/pyflakes/api.py#L211
    exit_codes=[0, 1],
)

"""
    Report Flake8 violations.
"""
flake8_driver = RegexBasedDriver(
    name="flake8",
    supported_extensions=["py"],
    command=["flake8"],
    # Match lines of the form:
    # new_file.py:1:17: E231 whitespace
    expression=r"^([^:]+):(\d+):(?:\d+): ([a-zA-Z]+\d+.*)$",
    command_to_check_install=["flake8", "--version"],
    # flake8 exit code is 1 if there are violations
    # http://flake8.pycqa.org/en/latest/user/invocation.html
    exit_codes=[0, 1],
)

jshint_driver = RegexBasedDriver(
    name="jshint",
    supported_extensions=["js"],
    command=["jshint"],
    expression=r"^([^:]+): line (\d+), col \d+, (.*)$",
    command_to_check_install=["jshint", "-v"],
)

shellcheck_driver = RegexBasedDriver(
    name="shellcheck",
    supported_extensions=["sh"],
    # Use gcc format to ease violations parsing
    command=["shellcheck", "-f", "gcc"],
    expression=r"^([^:]+):(\d+):(\d+: .*)$",
    command_to_check_install=["shellcheck", "-V"],
    # shellcheck exit code is 1 if there are violations
    # https://www.shellcheck.net/wiki/Integration#exit-codes
    exit_codes=[0, 1],
)


class EslintDriver(RegexBasedDriver):
    def __init__(self):
        super().__init__(
            name="eslint",
            supported_extensions=["js"],
            command=["eslint", "--format=compact"],
            expression=r"^([^:]+): line (\d+), col \d+, (.*)$",
            command_to_check_install=["eslint", "-v"],
        )
        self.report_root_path = None

    def add_driver_args(self, **kwargs):
        self.report_root_path = kwargs.pop("report_root_path", None)
        if kwargs:
            super().add_driver_args(**kwargs)

    def parse_reports(self, reports):
        violations_dict = super().parse_reports(reports)
        if self.report_root_path:
            keys = list(violations_dict.keys())
            for key in keys:
                new_key = os.path.relpath(key, self.report_root_path)
                violations_dict[new_key] = violations_dict.pop(key)
        return violations_dict


"""
    Report pydocstyle violations.

    Warning/error codes:
        D1**: Missing Docstrings
        D2**: Whitespace Issues
        D3**: Quotes Issues
        D4**: Docstring Content Issues

    http://www.pydocstyle.org/en/latest/error_codes.html
"""
pydocstyle_driver = RegexBasedDriver(
    name="pydocstyle",
    supported_extensions=["py"],
    command=["pydocstyle"],
    expression=r"^(.+?):(\d+).*?$.+?^        (.*?)$",
    command_to_check_install=["pydocstyle", "--version"],
    flags=re.MULTILINE | re.DOTALL,
    # pydocstyle exit code is 1 if there are violations
    # http://www.pydocstyle.org/en/2.1.1/usage.html#return-code
    exit_codes=[0, 1],
)


class PylintDriver(QualityDriver):
    def __init__(self):
        """
        args:
            expression: regex used to parse report
        See super for other args
        """
        super().__init__(
            "pylint",
            ["py"],
            [
                "pylint",
                '--msg-template="{path}:{line}: [{msg_id}({symbol}), {obj}] {msg}"',
            ],
            # Pylint returns bit-encoded exit codes as documented here:
            # https://pylint.readthedocs.io/en/latest/user_guide/run.html
            # 1 = fatal error, occurs if an error prevents pylint from doing further processing
            # 2,4,8,16 = error/warning/refactor/convention message issued
            # 32 = usage error
            [
                0,
                2,
                4,
                2 | 4,
                8,
                2 | 8,
                4 | 8,
                2 | 4 | 8,
                16,
                2 | 16,
                4 | 16,
                2 | 4 | 16,
                8 | 16,
                2 | 8 | 16,
                4 | 8 | 16,
                2 | 4 | 8 | 16,
            ],
        )
        self.pylint_expression = re.compile(
            r"^([^:]+):(\d+): \[(\w+),? ?([^\]]*)] (.*)$"
        )
        self.dupe_code_violation = "R0801"
        self.command_to_check_install = ["pylint", "--version"]

        # Match lines of the form:
        # path/to/file.py:123: [C0111] Missing docstring
        # path/to/file.py:456: [C0111, Foo.bar] Missing docstring
        self.multi_line_violation_regex = re.compile(r"==((?:\w|\.)+?):\[?(\d+)")
        self.dupe_code_violation_regex = re.compile(r"Similar lines in (\d+) files")

    def _process_dupe_code_violation(self, lines, current_line, message):
        """
        The duplicate code violation is a multi line error. This pulls out
        all the relevant files
        """
        src_paths = []
        message_match = self.dupe_code_violation_regex.match(message)
        if message_match:
            for _ in range(int(message_match.group(1))):
                current_line += 1
                match = self.multi_line_violation_regex.match(lines[current_line])
                src_path, l_number = match.groups()
                src_paths.append(("%s.py" % src_path, l_number))
        return src_paths

    def parse_reports(self, reports):
        """
        Args:
            reports: list[str] - output from the report
        Return:
            A dict[Str:Violation]
            Violation is a simple named tuple Defined above
        """
        violations_dict = defaultdict(list)
        for report in reports:
            output_lines = report.split("\n")

            for output_line_number, line in enumerate(output_lines):
                match = self.pylint_expression.match(line)

                # Ignore any line that isn't matched
                # (for example, snippets from the source code)
                if match is not None:
                    (
                        pylint_src_path,
                        line_number,
                        pylint_code,
                        function_name,
                        message,
                    ) = match.groups()
                    if pylint_code == self.dupe_code_violation:
                        files_involved = self._process_dupe_code_violation(
                            output_lines, output_line_number, message
                        )
                    else:
                        files_involved = [(pylint_src_path, line_number)]

                    for violation in files_involved:
                        pylint_src_path, line_number = violation
                        # pylint might uses windows paths
                        pylint_src_path = util.to_unix_path(pylint_src_path)
                        # If we're looking for a particular source file,
                        # ignore any other source files.
                        if function_name:
                            error_str = "{}: {}: {}".format(
                                pylint_code, function_name, message
                            )
                        else:
                            error_str = f"{pylint_code}: {message}"

                        violation = Violation(int(line_number), error_str)
                        violations_dict[pylint_src_path].append(violation)

        return violations_dict

    def installed(self):
        """
        Method checks if the provided tool is installed.
        Returns: boolean True if installed
        """
        return run_command_for_code(self.command_to_check_install) == 0


class CppcheckDriver(QualityDriver):
    """
    Driver for cppcheck c/c++ static analyzer.
    """

    def __init__(self):
        """
        args:
            expression: regex used to parse report
        See super for other args
        """
        super().__init__(
            "cppcheck",
            ["c", "cpp", "h", "hpp"],
            ["cppcheck", "--quiet"],
            output_stderr=True,
        )
        # Errors look like:
        # [src/foo.c:123]: (error) Array 'yolo[4]' accessed at index 4, which is out of bounds.
        # Match for everything, including ":" in the file name (first capturing
        # group), in case there are pathological path names with ":"
        self.cppcheck_expression = re.compile(r"^\[(.*?):(\d+)\]: (.*$)")
        self.command_to_check_install = ["cppcheck", "--version"]

    def parse_reports(self, reports):
        """
        Args:
            reports: list[str] - output from the report
        Return:
            A dict[Str:Violation]
            Violation is a simple named tuple Defined above
        """
        violations_dict = defaultdict(list)
        for report in reports:
            output_lines = report.splitlines()

            for line in output_lines:
                match = self.cppcheck_expression.match(line)

                # Ignore any line that isn't matched
                # (for example, snippets from the source code)
                if match is not None:
                    (cppcheck_src_path, line_number, message) = match.groups()

                    violation = Violation(int(line_number), message)
                    violations_dict[cppcheck_src_path].append(violation)

        return violations_dict

    def installed(self):
        """
        Method checks if the provided tool is installed.
        Returns: boolean True if installed
        """
        return run_command_for_code(self.command_to_check_install) == 0
