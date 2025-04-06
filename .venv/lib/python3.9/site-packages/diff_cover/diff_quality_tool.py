"""
Implement the command-line tool interface for diff_quality.
"""

import argparse
import io
import logging
import os
import sys

import pluggy

import diff_cover
from diff_cover import hookspecs
from diff_cover.config_parser import Tool, get_config
from diff_cover.diff_cover_tool import (
    COMPARE_BRANCH_HELP,
    CONFIG_FILE_HELP,
    CSS_FILE_HELP,
    DIFF_RANGE_NOTATION_HELP,
    EXCLUDE_HELP,
    FAIL_UNDER_HELP,
    HTML_REPORT_HELP,
    IGNORE_STAGED_HELP,
    IGNORE_UNSTAGED_HELP,
    IGNORE_WHITESPACE,
    INCLUDE_UNTRACKED_HELP,
    JSON_REPORT_HELP,
    MARKDOWN_REPORT_HELP,
    QUIET_HELP,
)
from diff_cover.diff_reporter import GitDiffReporter
from diff_cover.git_diff import GitDiffTool
from diff_cover.git_path import GitPathTool
from diff_cover.report_generator import (
    HtmlQualityReportGenerator,
    JsonReportGenerator,
    MarkdownQualityReportGenerator,
    StringQualityReportGenerator,
)
from diff_cover.violationsreporters.base import QualityReporter
from diff_cover.violationsreporters.java_violations_reporter import (
    CheckstyleXmlDriver,
    FindbugsXmlDriver,
    PmdXmlDriver,
    checkstyle_driver,
)
from diff_cover.violationsreporters.violations_reporter import (
    CppcheckDriver,
    EslintDriver,
    PylintDriver,
    flake8_driver,
    jshint_driver,
    pycodestyle_driver,
    pydocstyle_driver,
    pyflakes_driver,
    shellcheck_driver,
)

QUALITY_DRIVERS = {
    "cppcheck": CppcheckDriver(),
    "pycodestyle": pycodestyle_driver,
    "pyflakes": pyflakes_driver,
    "pylint": PylintDriver(),
    "flake8": flake8_driver,
    "jshint": jshint_driver,
    "eslint": EslintDriver(),
    "pydocstyle": pydocstyle_driver,
    "checkstyle": checkstyle_driver,
    "checkstylexml": CheckstyleXmlDriver(),
    "findbugs": FindbugsXmlDriver(),
    "pmd": PmdXmlDriver(),
    "shellcheck": shellcheck_driver,
}

VIOLATION_CMD_HELP = "Which code quality tool to use (%s)" % "/".join(
    sorted(QUALITY_DRIVERS)
)
INPUT_REPORTS_HELP = "Which violations reports to use"
OPTIONS_HELP = "Options to be passed to the violations tool"
INCLUDE_HELP = "Files to include (glob pattern)"
REPORT_ROOT_PATH_HELP = "The root path used to generate a report"


LOGGER = logging.getLogger(__name__)


def parse_quality_args(argv):
    """
    Parse command line arguments, returning a dict of
    valid options:

        {
            'violations': pycodestyle| pyflakes | flake8 | pylint | ...,
            'html_report': None | HTML_REPORT,
            'external_css_file': None | CSS_FILE,
        }

    where `HTML_REPORT` and `CSS_FILE` are paths.
    """
    parser = argparse.ArgumentParser(description=diff_cover.QUALITY_DESCRIPTION)

    parser.add_argument(
        "--violations", metavar="TOOL", type=str, help=VIOLATION_CMD_HELP, required=True
    )

    parser.add_argument(
        "--html-report",
        metavar="FILENAME",
        type=str,
        help=HTML_REPORT_HELP,
    )

    parser.add_argument(
        "--json-report",
        metavar="FILENAME",
        type=str,
        help=JSON_REPORT_HELP,
    )

    parser.add_argument(
        "--markdown-report",
        metavar="FILENAME",
        type=str,
        help=MARKDOWN_REPORT_HELP,
    )

    parser.add_argument(
        "--external-css-file",
        metavar="FILENAME",
        type=str,
        help=CSS_FILE_HELP,
    )

    parser.add_argument(
        "--compare-branch",
        metavar="BRANCH",
        type=str,
        help=COMPARE_BRANCH_HELP,
    )

    parser.add_argument("input_reports", type=str, nargs="*", help=INPUT_REPORTS_HELP)

    parser.add_argument("--options", type=str, nargs="?", help=OPTIONS_HELP)

    parser.add_argument(
        "--fail-under", metavar="SCORE", type=float, help=FAIL_UNDER_HELP
    )

    parser.add_argument(
        "--ignore-staged", action="store_true", default=None, help=IGNORE_STAGED_HELP
    )

    parser.add_argument(
        "--ignore-unstaged",
        action="store_true",
        default=None,
        help=IGNORE_UNSTAGED_HELP,
    )

    parser.add_argument(
        "--include-untracked",
        action="store_true",
        default=None,
        help=INCLUDE_UNTRACKED_HELP,
    )

    parser.add_argument(
        "--exclude", metavar="EXCLUDE", type=str, nargs="+", help=EXCLUDE_HELP
    )

    parser.add_argument(
        "--include", metavar="INCLUDE", nargs="+", type=str, help=INCLUDE_HELP
    )

    parser.add_argument(
        "--diff-range-notation",
        metavar="RANGE_NOTATION",
        type=str,
        help=DIFF_RANGE_NOTATION_HELP,
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"diff-quality {diff_cover.VERSION}",
    )
    parser.add_argument(
        "--ignore-whitespace",
        action="store_true",
        default=None,
        help=IGNORE_WHITESPACE,
    )

    parser.add_argument(
        "-q", "--quiet", action="store_true", default=None, help=QUIET_HELP
    )

    parser.add_argument(
        "-c", "--config-file", help=CONFIG_FILE_HELP, metavar="CONFIG_FILE"
    )

    parser.add_argument(
        "--report-root-path", help=REPORT_ROOT_PATH_HELP, metavar="ROOT_PATH"
    )

    defaults = {
        "ignore_whitespace": False,
        "compare_branch": "origin/main",
        "diff_range_notation": "...",
        "input_reports": [],
        "fail_under": 0,
        "ignore_staged": False,
        "ignore_unstaged": False,
        "ignore_untracked": False,
        "quiet": False,
    }

    return get_config(
        parser=parser, argv=argv, defaults=defaults, tool=Tool.DIFF_QUALITY
    )


def generate_quality_report(
    tool,
    compare_branch,
    html_report=None,
    json_report=None,
    markdown_report=None,
    css_file=None,
    ignore_staged=False,
    ignore_unstaged=False,
    include_untracked=False,
    exclude=None,
    include=None,
    diff_range_notation=None,
    ignore_whitespace=False,
    quiet=False,
):
    """
    Generate the quality report, using kwargs from `parse_args()`.
    """
    supported_extensions = (
        getattr(tool, "supported_extensions", None) or tool.driver.supported_extensions
    )
    diff = GitDiffReporter(
        compare_branch,
        git_diff=GitDiffTool(diff_range_notation, ignore_whitespace),
        ignore_staged=ignore_staged,
        ignore_unstaged=ignore_unstaged,
        include_untracked=include_untracked,
        supported_extensions=supported_extensions,
        exclude=exclude,
        include=include,
    )

    if html_report is not None:
        css_url = css_file
        if css_url is not None:
            css_url = os.path.relpath(css_file, os.path.dirname(html_report))
        reporter = HtmlQualityReportGenerator(tool, diff, css_url=css_url)
        with open(html_report, "wb") as output_file:
            reporter.generate_report(output_file)
        if css_file is not None:
            with open(css_file, "wb") as output_file:
                reporter.generate_css(output_file)

    if json_report is not None:
        reporter = JsonReportGenerator(tool, diff)
        with open(json_report, "wb") as output_file:
            reporter.generate_report(output_file)

    if markdown_report is not None:
        reporter = MarkdownQualityReportGenerator(tool, diff)
        with open(markdown_report, "wb") as output_file:
            reporter.generate_report(output_file)

    # Generate the report for stdout
    reporter = StringQualityReportGenerator(tool, diff)
    output_file = io.BytesIO() if quiet else sys.stdout.buffer
    reporter.generate_report(output_file)

    return reporter.total_percent_covered()


def main(argv=None, directory=None):
    """
    Main entry point for the tool, script installed via pyproject.toml
    Returns a value that can be passed into exit() specifying
    the exit code.
    1 is an error
    0 is successful run
    """

    argv = argv or sys.argv
    arg_dict = parse_quality_args(argv[1:])

    quiet = arg_dict["quiet"]
    level = logging.ERROR if quiet else logging.WARNING
    logging.basicConfig(format="%(message)s", level=level)

    GitPathTool.set_cwd(directory)
    fail_under = arg_dict.get("fail_under")
    tool = arg_dict["violations"]
    user_options = arg_dict.get("options")
    if user_options:
        # strip quotes if present
        first_char = user_options[0]
        last_char = user_options[-1]
        if first_char == last_char and first_char in ('"', "'"):
            user_options = user_options[1:-1]
    reporter = None
    reporter_factory_fn = None
    driver = QUALITY_DRIVERS.get(tool)
    if driver is None:
        # The requested tool is not built into diff_cover. See if another Python
        # package provides it.
        plugin_manager = pluggy.PluginManager("diff_cover")
        plugin_manager.add_hookspecs(hookspecs)
        plugin_manager.load_setuptools_entrypoints("diff_cover")

        hooks = (
            plugin_manager.hook.diff_cover_report_quality  # pylint: disable=no-member
        )
        for hookimpl in hooks.get_hookimpls():
            if hookimpl.plugin_name == tool:
                reporter_factory_fn = hookimpl.function
                break

    if reporter or driver or reporter_factory_fn:
        input_reports = []
        try:
            for path in arg_dict["input_reports"]:
                try:
                    input_reports.append(open(path, "rb"))
                except OSError:
                    LOGGER.error("Could not load report '%s'", path)
                    return 1
            if driver is not None:
                # If we've been given pre-generated reports,
                # try to open the files
                if arg_dict["report_root_path"]:
                    driver.add_driver_args(
                        report_root_path=arg_dict["report_root_path"]
                    )

                reporter = QualityReporter(driver, input_reports, user_options)
            elif reporter_factory_fn:
                reporter = reporter_factory_fn(
                    reports=input_reports, options=user_options
                )

            percent_passing = generate_quality_report(
                reporter,
                arg_dict["compare_branch"],
                html_report=arg_dict["html_report"],
                json_report=arg_dict["json_report"],
                markdown_report=arg_dict["markdown_report"],
                css_file=arg_dict["external_css_file"],
                ignore_staged=arg_dict["ignore_staged"],
                ignore_unstaged=arg_dict["ignore_unstaged"],
                include_untracked=arg_dict["include_untracked"],
                exclude=arg_dict["exclude"],
                include=arg_dict["include"],
                diff_range_notation=arg_dict["diff_range_notation"],
                ignore_whitespace=arg_dict["ignore_whitespace"],
                quiet=quiet,
            )
            if percent_passing >= fail_under:
                return 0

            LOGGER.error("Failure. Quality is below %i.", fail_under)
            return 1

        except ImportError:
            LOGGER.error("Quality tool not installed: '%s'", tool)
            return 1
        except OSError as exc:
            LOGGER.error("Failure: '%s'", str(exc))
            return 1
        # Close any reports we opened
        finally:
            for file_handle in input_reports:
                file_handle.close()

    else:
        LOGGER.error("Quality tool not recognized: '%s'", tool)
        return 1


if __name__ == "__main__":
    sys.exit(main())
