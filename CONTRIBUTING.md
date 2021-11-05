# Contribution Guidelines

## General workflow

1. Fork the [CoinAlpha/hummingbot](https://github.com/CoinAlpha/hummingbot) repository.
2. Create a new branch from the `development` branch in your fork.
3. Make commits to your branch.
4. When you have finished with your fix / feature / connector / documentation:

    - Rebase upstream changes into your branch
    - Create a pull request to the `development` branch
    - Include a description of your changes
    - Ensure to **Allow edits by maintainers** before submitting the pull request

5. Your code changes will be reviewed by Hummingbot's development team and tested by the QA team.
6. Fix any changes requested by your reviewer, fix issues raised by a tester, and push your fixes as a single new commit.
7. Once the pull request has been reviewed and accepted; it will be merged by a member of the Hummingbot development team.

**NOTE:** Tests are very important. Submit tests if your pull request contains new, testable behavior. See [Unit test coverage](#unit-test-coverage) for more information.

## Detailed workflow

### 1. Fork the repository

Use GitHub's interface to make a fork of the repo, add the Hummingbot repo as an upstream remote, and fetch upstream data:

```
git remote add upstream https://github.com/CoinAlpha/hummingbot.git
git fetch upstream
```

### 2. Creating your branch

Create your local branch and should follow this naming convention:

- feat/ ...
- fix/ ...
- refactor/ ...
- doc/ ...

Create and switch to a new local branch called `feat/[branch_name]` based on `development` of the remote `upstream`.

```
git checkout -b feat/[branch_name] upstream/development
```

### 3. Commit changes to a branch

Make commits to your branch. Prefix each commit like so:

- (feat) add a new feature
- (fix) fix inconsistent tests
- (refactor) ...
- (cleanup) ...
- (doc) ...

Make changes and commits on your branch, and make sure that you only make relevant changes. If you find yourself making unrelated changes, create a new branch for those changes.

Commit message guidelines:

- Commit messages should be written in the present tense, e.g. "(feat) add unit tests".
- The first line of your commit message should be a summary of what the commit changes. Aim for about 70 characters max. Remember: This is a summary, not a detailed description of everything that changed.
- If you want to explain the commit in more depth, following the first line should be blank and then a more detailed description of the commit. This can be as detailed as you want, so dig into details here and keep the first line short.

### 4. Rebase upstream changes

Once you are done making changes, you can begin the process of getting
your code merged into the main repo. Step 1 is to rebase upstream
changes to the `development` branch into yours by running this command
from your branch:

```bash
git pull --rebase upstream development
```

This will start the rebase process. You must commit all of your changes
before doing this. If there are no conflicts, this should just roll all
of your changes back on top of the changes from upstream, leading to a
nice, clean, linear commit history.

If there are conflicting changes, git will start yelling at you part way
through the rebasing process. Git will pause rebasing to allow you to sort
out the conflicts. You do this the same way you solve merge conflicts,
by checking all of the files git says have been changed in both histories
and picking the versions you want. Be aware that these changes will show
up in your pull request, so try and incorporate upstream changes as much
as possible.

You pick a file by `git add`ing it - you do not make commits during a
rebase.

Once you are done fixing conflicts for a specific commit, run:

```bash
git rebase --continue
```

This will continue the rebasing process. Once you are done fixing all
conflicts you should run the existing tests to make sure you didn’t break
anything, then run your new tests (there are new tests, right?) and
make sure they work also.

If rebasing broke anything, fix it, then repeat the above process until
you get here again and nothing is broken and all the tests pass.

### 5. Create a pull request

Make a clear pull request from your fork and branch to the upstream `development`
branch, detailing exactly what changes you made and what feature this
should add. The clearer your pull request is the faster you can get
your changes incorporated into this repo.

It is important to check **Allow edits by maintainers** for the Hummingbot team to update your branch with `development` whenever needed.

![Creating a pull request](documentation/docs/assets/img/pull-request-sample.png)

If the development team requests changes, you should make more commits to your
branch to address these, then follow this process again from rebasing onwards.

Once you get back here, make a comment requesting further review and
someone will look at your code again. If it addresses the requests, it will
get merged, else, just repeat again.

Thanks for contributing!

## Unit test coverage

It is required to present a minimum 75% unit test coverage of all the changes included in a pull request. Some components are, however, excluded from this validation (for example all UI components).

To calculate the diff-coverage locally on your computer, run `make development-diff-cover` after running all tests.

## Checklist:

This is just to help you organize your process

- [ ] Did I create my branch from `development` (don't create new branches from existing feature branches)?
- [ ] Did I follow the correct naming convention for my branch?
- [ ] Is my branch focused on a single main change?
  - [ ] Do all of my changes directly relate to this change?
- [ ] Did I rebase the upstream `development` branch after I finished all my
  work?
- [ ] Did I write a clear pull request message detailing what changes I made?
- [ ] Did I get a code review?
  - [ ] Did I make any requested changes from that code review?

If you follow all of these guidelines and make good changes, you should have no problem getting your changes merged in.
