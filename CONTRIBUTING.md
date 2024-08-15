# Contribution Guidelines

## General Workflow

1. Fork the `hummingbot/hummingbot` repository.
2. Create a new branch from the `development` branch in your fork.
3. Commit your changes to your branch.
4. Once you've completed your fix, feature, connector, or documentation:

   - Rebase upstream changes into your branch.
   - Create a pull request to the `development` branch.
   - Include a detailed description of your changes.
   - Ensure to `allow edits by maintainers` before submitting the pull request.

5. Your code changes will be reviewed and tested by the Foundation QA team.
6. Address any changes requested by your reviewer, fix issues raised, and push your fixes as a single new commit.
7. Once the pull request has been reviewed and accepted, it will be merged by a member of the Hummingbot Foundation team.

**Note:** Tests are crucial. If your pull request contains new, testable behavior, please submit tests. Refer to the 'Unit Test Coverage' section for more information.

## Detailed Workflow

### 1. Fork the Repository

Use GitHub's interface to fork the repo, add the Hummingbot repo as an upstream remote, and fetch upstream data:

```bash
git remote add upstream https://github.com/hummingbot/hummingbot.git
git fetch upstream
```

### 2. Create Your Branch

Create your local branch following this naming convention:

- feat/...
- fix/...
- refactor/...
- doc/...

Create and switch to a new local branch called feat/[branch_name] based on the development branch of the remote upstream:

```bash
git checkout -b feat/[branch_name] upstream/development
```

### 3. Commit Changes to Your Branch

Make commits to your branch. Prefix each commit like so:

- (feat) add a new feature
- (fix) fix inconsistent tests
- (refactor) ...
- (cleanup) ...
- (doc) ...

Commit messages should be written in the present tense, e.g., "(feat) add unit tests". The first line of your commit message should be a summary of what the commit changes, aiming for about 70 characters max. If you want to explain the commit in more depth, provide a more detailed description after a blank line following the first line.

### 4. Rebase Upstream Changes

Rebase upstream changes to the development branch into yours by running this command from your branch:

```bash
git pull --rebase upstream development
```

If there are conflicting changes, git will pause rebasing to allow you to sort out the conflicts. Once you are done fixing conflicts for a specific commit, run:

```bash
git rebase --continue
```

Ensure all tests pass after rebasing.

### 5. Create a Pull Request

Create a clear pull request from your fork and branch to the upstream `development` branch, detailing your changes. Check 'Allow edits by maintainers' for the Foundation team to update your branch with development whenever needed.

If the Foundation team requests changes, make more commits to your branch to address these, then follow this process again from rebasing onwards. Once you've addressed the requests, request further review.

## Unit Test Coverage

A minimum of 80% unit test coverage is required for all changes included in a pull request. However, some components, like UI components, are excluded from this validation.

To run tests locally, run `make test` after activating the environment.

To calculate the diff-coverage locally on your computer, run `make development-diff-cover` after running all tests.

## Checklist

- Did I create my branch from `development` (don't create new branches from existing feature branches)?
- Did I follow the correct naming convention for my branch?
- Is my branch focused on a single main change?
- Do all of my changes directly relate to this change?
- Did I rebase the upstream development branch after I finished all my work?
- Did I write a clear pull request message detailing what changes I made?
- Did I get a code review?
- Did I make any requested changes from that code review?

If you adhere to these guidelines and make quality changes, you should have no problems getting your contributions accepted. Thank you for contributing!
