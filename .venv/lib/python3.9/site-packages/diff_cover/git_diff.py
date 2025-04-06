"""
Wrapper for `git diff` command.
"""

from textwrap import dedent

from diff_cover.command_runner import CommandError, execute


class GitDiffError(Exception):
    """
    `git diff` command produced an error.
    """


class GitDiffTool:
    """
    Thin wrapper for a subset of the `git diff` command.
    """

    def __init__(self, range_notation, ignore_whitespace):
        """
        :param str range_notation:
            which range notation to use when producing the diff for committed
            files against another branch.

            Traditionally in git-cover the symmetric difference (three-dot, "A...M") notation has
            been used:
            it includes commits reachable from A and M from their merge-base, but not both,
            taking history in account.
            This includes cherry-picks between A and M, which are harmless and do not produce
            changes, but might give inaccurate coverage false-negatives.

            Two-dot range notation ("A..M") compares the tips of both trees and produces a diff.
            This more accurately describes the actual patch that will be applied by merging A into
            M, even if commits have been cherry-picked between branches.
            This will produce a more accurate diff for coverage comparison when complex merges and
            cherry-picks are involved.

         :param bool ignore_whitespace:
            Perform a diff but ignore any and all whitespace.
        """
        self.range_notation = range_notation
        self._default_git_args = [
            "git",
            "-c",
            "diff.mnemonicprefix=no",
            "-c",
            "diff.noprefix=no",
        ]

        self._default_diff_args = ["diff", "--no-color", "--no-ext-diff", "-U0"]

        if ignore_whitespace:
            self._default_diff_args.append("--ignore-all-space")
            self._default_diff_args.append("--ignore-blank-lines")

    def diff_committed(self, compare_branch="origin/main"):
        """
        Returns the output of `git diff` for committed
        changes not yet in origin/main.

        Raises a `GitDiffError` if `git diff` outputs anything
        to stderr.
        """
        diff_range = "{branch}{notation}HEAD".format(
            branch=compare_branch, notation=self.range_notation
        )
        try:
            return execute(
                self._default_git_args + self._default_diff_args + [diff_range]
            )[0]
        except CommandError as e:
            if "unknown revision" in str(e):
                raise ValueError(
                    dedent(
                        f"""
                        Could not find the branch to compare to. Does '{compare_branch}' exist?
                        the `--compare-branch` argument allows you to set a different branch.
                    """
                    )
                )
            raise

    def diff_unstaged(self):
        """
        Returns the output of `git diff` with no arguments, which
        is the diff for unstaged changes.

        Raises a `GitDiffError` if `git diff` outputs anything
        to stderr.
        """
        return execute(self._default_git_args + self._default_diff_args)[0]

    def diff_staged(self):
        """
        Returns the output of `git diff --cached`, which
        is the diff for staged changes.

        Raises a `GitDiffError` if `git diff` outputs anything
        to stderr.
        """
        return execute(self._default_git_args + self._default_diff_args + ["--cached"])[
            0
        ]

    def untracked(self):
        """Return the untracked files."""
        output = execute(["git", "ls-files", "--exclude-standard", "--others"])[0]
        if not output:
            return []
        return [line for line in output.splitlines() if line]


class GitDiffFileTool(GitDiffTool):

    def __init__(self, diff_file_path):

        self.diff_file_path = diff_file_path
        super().__init__("...", False)

    def diff_committed(self, compare_branch="origin/main"):
        """
        Returns the contents of a diff file.

        Raises a `GitDiffError` if the file cannot be read.
        """
        try:
            with open(self.diff_file_path, "r") as file:
                return file.read()
        except IOError as e:
            raise ValueError(
                dedent(
                    f"""
                    Could not read the diff file. Make sure '{self.diff_file_path}' exists?
                    """
                )
            )

    def diff_unstaged(self):
        return ""

    def diff_staged(self):
        return ""

    def untracked(self):
        return ""
