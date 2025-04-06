"""
Classes for querying which lines have changed based on a diff.
"""

import fnmatch
import glob
import os
import re
from abc import ABC, abstractmethod

from diff_cover.git_diff import GitDiffError


class BaseDiffReporter(ABC):
    """
    Query information about lines changed in a diff.
    """

    _exclude = None
    _include = None

    def __init__(self, name, exclude=None, include=None):
        """
        Provide a `name` for the diff report, which will
        be included in the diff coverage report.
        """
        self._name = name
        self._exclude = exclude
        self._include = include

    @abstractmethod
    def src_paths_changed(self):
        """
        Returns a list of source paths changed in this diff.

        Source paths are guaranteed to be unique.
        """

    @abstractmethod
    def lines_changed(self, src_path):
        """
        Returns a list of line numbers changed in the
        source file at `src_path`.

        Each line is guaranteed to be included only once in the list
        and in ascending order.
        """

    def name(self):
        """
        Return the name of the diff, which will be included
        in the diff coverage report.
        """
        return self._name

    def _fnmatch(self, filename, patterns, default=True):
        """Wrap :func:`fnmatch.fnmatch` to add some functionality.

        :param str filename:
            Name of the file we're trying to match.
        :param list patterns:
            Patterns we're using to try to match the filename.
        :param bool default:
            The default value if patterns is empty
        :returns:
            True if a pattern matches the filename, False if it doesn't.
            ``default`` if patterns is empty.
        """
        if not patterns:
            return default
        return any(fnmatch.fnmatch(filename, pattern) for pattern in patterns)

    def _is_path_excluded(self, path):
        """
        Check if a path is excluded.

        First it is checked if the path matches one of the include patterns (if provided).
        Second, the path is matched against the exclude patterns.

        :param str path:
            Path to check against the exclude and include patterns.
        :returns:
            True if the patch should be excluded, otherwise False.
        """
        include = self._include
        if include:
            for pattern in include:
                if path in glob.glob(pattern, recursive=True):
                    break  # file is included
            else:
                return True

        exclude = self._exclude
        if not exclude:
            return False
        basename = os.path.basename(path)
        if self._fnmatch(basename, exclude):
            return True

        absolute_path = os.path.abspath(path)
        return self._fnmatch(absolute_path, exclude)


class GitDiffReporter(BaseDiffReporter):
    """
    Query information from a Git diff between branches.
    """

    def __init__(
        self,
        compare_branch="origin/main",
        git_diff=None,
        ignore_staged=None,
        ignore_unstaged=None,
        include_untracked=False,
        supported_extensions=None,
        exclude=None,
        include=None,
    ):
        """
        Configure the reporter to use `git_diff` as the wrapper
        for the `git diff` tool.  (Should have same interface
        as `git_diff.GitDiffTool`)
        """
        options = []
        if not ignore_staged:
            options.append("staged")
        if not ignore_unstaged:
            options.append("unstaged")
        if include_untracked:
            options.append("untracked")

        # Branch is always present, so use as basis for name
        name = f"{compare_branch}{git_diff.range_notation if git_diff else '...'}HEAD"
        if len(options) > 0:
            # If more options are present separate them by comma's, except the last one
            for item in options[:-1]:
                name += ", " + item
            # Apply and + changes to the last option
            name += " and " + options[-1] + " changes"

        super().__init__(name, exclude, include)

        self._compare_branch = compare_branch
        self._git_diff_tool = git_diff
        self._ignore_staged = ignore_staged
        self._ignore_unstaged = ignore_unstaged
        self._include_untracked = include_untracked
        self._supported_extensions = supported_extensions

        # Cache diff information as a dictionary
        # with file path keys and line number list values
        self._diff_dict = None

    def clear_cache(self):
        """
        Reset the git diff result cache.
        """
        self._diff_dict = None

    def src_paths_changed(self):
        """
        See base class docstring.
        """

        # Get the diff dictionary
        diff_dict = self._git_diff()
        # include untracked files
        if self._include_untracked:
            for path in self._git_diff_tool.untracked():
                if not self._validate_path_to_diff(path):
                    continue

                num_lines = self._get_file_lines(path)
                diff_dict[path] = list(range(1, num_lines + 1))

        # Return the changed file paths (dict keys)
        # in alphabetical order
        return sorted(diff_dict.keys(), key=lambda x: x.lower())

    @staticmethod
    def _get_file_lines(path):
        """
        Return the number of lines in a file.
        """

        try:
            with open(path, encoding="utf-8") as file_handle:
                return len(file_handle.readlines())
        except UnicodeDecodeError:
            return 0

    def lines_changed(self, src_path):
        """
        See base class docstring.
        """

        # Get the diff dictionary (cached)
        diff_dict = self._git_diff()

        # Look up the modified lines for the source file
        # If no lines modified, return an empty list
        return diff_dict.get(src_path, [])

    def _get_included_diff_results(self):
        """
        Return a list of stages to be included in the diff results.
        """
        included = [self._git_diff_tool.diff_committed(self._compare_branch)]
        if not self._ignore_staged:
            included.append(self._git_diff_tool.diff_staged())
        if not self._ignore_unstaged:
            included.append(self._git_diff_tool.diff_unstaged())

        return included

    def _git_diff(self):
        """
        Run `git diff` and returns a dict in which the keys
        are changed file paths and the values are lists of
        line numbers.

        Guarantees that each line number within a file
        is unique (no repeats) and in ascending order.

        Returns a cached result if called multiple times.

        Raises a GitDiffError if `git diff` has an error.
        """

        # If we do not have a cached result, execute `git diff`
        if self._diff_dict is None:
            result_dict = {}

            for diff_str in self._get_included_diff_results():
                # Parse the output of the diff string
                diff_dict = self._parse_diff_str(diff_str)

                for src_path, (added_lines, deleted_lines) in diff_dict.items():
                    if not self._validate_path_to_diff(src_path):
                        continue

                    # Remove any lines from the dict that have been deleted
                    # Include any lines that have been added
                    result_dict[src_path] = [
                        line
                        for line in result_dict.get(src_path, [])
                        if line not in deleted_lines
                    ] + added_lines

            # Eliminate repeats and order line numbers
            for src_path, lines in result_dict.items():
                result_dict[src_path] = self._unique_ordered_lines(lines)

            # Store the resulting dict
            self._diff_dict = result_dict

        # Return the diff cache
        return self._diff_dict

    def _validate_path_to_diff(self, src_path: str) -> bool:
        """
        Validate if a path should be included in the diff.

        Returns True if the path should be included, otherwise False.

        A path should be excluded if:
        - If the path is excluded
        - If the path has an extension that is not supported
        """

        if self._is_path_excluded(src_path):
            return False

        # If no _supported_extensions provided, or extension present: process
        _, extension = os.path.splitext(src_path)
        extension = extension[1:].lower()

        if self._supported_extensions and extension not in self._supported_extensions:
            return False

        return True

    # Regular expressions used to parse the diff output
    SRC_FILE_RE = re.compile(r'^diff --git "?a/.*"? "?b/([^\n"]*)"?')
    MERGE_CONFLICT_RE = re.compile(r"^diff --cc ([^\n]*)")
    HUNK_LINE_RE = re.compile(r"\+([0-9]*)")

    def _parse_diff_str(self, diff_str):
        """
        Parse the output of `git diff` into a dictionary of the form:

            { SRC_PATH: (ADDED_LINES, DELETED_LINES) }

        where `ADDED_LINES` and `DELETED_LINES` are lists of line
        numbers added/deleted respectively.

        If the output could not be parsed, raises a GitDiffError.
        """

        # Create a dict to hold results
        diff_dict = {}

        # Parse the diff string into sections by source file
        sections_dict = self._parse_source_sections(diff_str)
        for src_path, diff_lines in sections_dict.items():
            # Parse the hunk information for the source file
            # to determine lines changed for the source file
            diff_dict[src_path] = self._parse_lines(diff_lines)

        return diff_dict

    def _parse_source_sections(self, diff_str):
        """
        Given the output of `git diff`, return a dictionary
        with keys that are source file paths.

        Each value is a list of lines from the `git diff` output
        related to the source file.

        Raises a `GitDiffError` if `diff_str` is in an invalid format.
        """

        # Create a dict to map source files to lines in the diff output
        source_dict = {}

        # Keep track of the current source file
        src_path = None

        # Signal that we've found a hunk (after starting a source file)
        found_hunk = False

        # Parse the diff string into sections by source file
        for line in diff_str.split("\n"):
            # If the line starts with "diff --git"
            # or "diff --cc" (in the case of a merge conflict)
            # then it is the start of a new source file
            if line.startswith("diff --git") or line.startswith("diff --cc"):
                # Retrieve the name of the source file
                src_path = self._parse_source_line(line)

                # Create an entry for the source file, if we don't
                # already have one.
                if src_path not in source_dict:
                    source_dict[src_path] = []

                # Signal that we're waiting for a hunk for this source file
                found_hunk = False

            # Every other line is stored in the dictionary for this source file
            # once we find a hunk section
            else:
                # Only add lines if we're in a hunk section
                # (ignore index and files changed lines)
                if found_hunk or line.startswith("@@"):
                    # Remember that we found a hunk
                    found_hunk = True

                    if src_path is not None:
                        source_dict[src_path].append(line)

                    else:
                        # We tolerate other information before we have
                        # a source file defined, unless it's a hunk line
                        if line.startswith("@@"):
                            msg = f"Hunk has no source file: '{line}'"
                            raise GitDiffError(msg)

        return source_dict

    def _parse_lines(self, diff_lines):
        """
        Given the diff lines output from `git diff` for a particular
        source file, return a tuple of `(ADDED_LINES, DELETED_LINES)`

        where `ADDED_LINES` and `DELETED_LINES` are lists of line
        numbers added/deleted respectively.

        Raises a `GitDiffError` if the diff lines are in an invalid format.
        """

        added_lines = []
        deleted_lines = []

        current_line_new = None
        current_line_old = None

        for line in diff_lines:
            # If this is the start of the hunk definition, retrieve
            # the starting line number
            if line.startswith("@@"):
                line_num = self._parse_hunk_line(line)
                current_line_new, current_line_old = line_num, line_num

            # This is an added/modified line, so store the line number
            elif line.startswith("+"):
                # Since we parse for source file sections before
                # calling this method, we're guaranteed to have a source
                # file specified.  We check anyway just to be safe.
                if current_line_new is not None:
                    # Store the added line
                    added_lines.append(current_line_new)

                    # Increment the line number in the file
                    current_line_new += 1

            # This is a deleted line that does not exist in the final
            # version, so skip it
            elif line.startswith("-"):
                # Since we parse for source file sections before
                # calling this method, we're guaranteed to have a source
                # file specified.  We check anyway just to be safe.
                if current_line_old is not None:
                    # Store the deleted line
                    deleted_lines.append(current_line_old)

                    # Increment the line number in the file
                    current_line_old += 1

            # This is a line in the final version that was not modified.
            # Increment the line number, but do not store this as a changed
            # line.
            else:
                if current_line_old is not None:
                    current_line_old += 1

                if current_line_new is not None:
                    current_line_new += 1

                # If we are not in a hunk, then ignore the line

        return added_lines, deleted_lines

    def _parse_source_line(self, line):
        """
        Given a source line in `git diff` output, return the path
        to the source file.
        """
        if "--git" in line:
            regex = self.SRC_FILE_RE
        elif "--cc" in line:
            regex = self.MERGE_CONFLICT_RE
        else:
            msg = f"Do not recognize format of source in line '{line}'"
            raise GitDiffError(msg)

        # Parse for the source file path
        groups = regex.findall(line)

        if len(groups) == 1:
            return groups[0]

        msg = f"Could not parse source path in line '{line}'"
        raise GitDiffError(msg)

    def _parse_hunk_line(self, line):
        """
        Given a hunk line in `git diff` output, return the line number
        at the start of the hunk.  A hunk is a segment of code that
        contains changes.

        The format of the hunk line is:

            @@ -k,l +n,m @@ TEXT

        where `k,l` represent the start line and length before the changes
        and `n,m` represent the start line and length after the changes.

        `git diff` will sometimes put a code excerpt from within the hunk
        in the `TEXT` section of the line.
        """
        # Split the line at the @@ terminators (start and end of the line)
        components = line.split("@@")

        # The first component should be an empty string, because
        # the line starts with '@@'.  The second component should
        # be the hunk information, and any additional components
        # are excerpts from the code.
        if len(components) >= 2:
            hunk_info = components[1]
            groups = self.HUNK_LINE_RE.findall(hunk_info)

            if len(groups) == 1:
                try:
                    return int(groups[0])

                except ValueError:
                    msg = f"Could not parse '{groups[0]}' as a line number"
                    raise GitDiffError(msg)

            else:
                msg = f"Could not find start of hunk in line '{line}'"
                raise GitDiffError(msg)

        else:
            msg = f"Could not parse hunk in line '{line}'"
            raise GitDiffError(msg)

    @staticmethod
    def _unique_ordered_lines(line_numbers):
        """
        Given a list of line numbers, return a list in which each line
        number is included once and the lines are ordered sequentially.
        """

        if len(line_numbers) == 0:
            return []

        # Ensure lines are unique by putting them in a set
        line_set = set(line_numbers)

        # Retrieve the list from the set, sort it, and return
        return sorted(line for line in line_set)
