
# Change History & Release Notes

## 2.21.0 add `string[]` to `LogOptions` type

- Adds `string[]` to the set of types supported as options for `git.log`
- Fix readme typos 

## 2.20.1 Bug-fix: `LogOptions` type definition

- `LogOptions` should be intersection rather than union types

## 2.19.0 - Upgrade task option filters

- move the command/task option processing function to TypeScript

## 2.18.0 - Upgrade Clone / Mirror tasks

- `git.clone` and `git.mirror` rewritten to fit the TypeScript tasks style.
- resolves issue whereby `git.clone` didn't accept an object of options despite being documented as supporting.

## 2.17.0 - Add remote message parsing to `git pull`

- `git pull` (and by extension `git merge`) adds remote message parsing to the `PullResult` type
- Remote message parsing adds property `remoteMessages.objects` of type `RemoteMessagesObjectEnumeration` to capture the  objects transferred in fetch and push.

## 2.16.0 - Upgrade Move task

- `git.mv` rewritten to fit the TypeScript tasks style.
- set up github actions for CI

## 2.15.0 - Task parsers automatically have access to `stdErr` as well as `stdOut` 

- adds the `TaskParser` type to describe a task's parser function and creates the `LineParser` utility to simplify line-by-line parsing of string responses.
- renames some interfaces for consistency of naming, the original name remains as a type alias marked as `@deprecated` until version 3.x:
  - BranchDeletionSummary > BranchSingleDeleteResult
  - BranchDeletionBatchSummary > BranchMultiDeleteResult
  - MergeSummary > MergeResult

## 2.14.0 - Bug fix: `git.checkoutBranch` fails to pass commands to git child process

- resolves an issue whereby the `git.checkoutBranch` method would not pass the branch detail through to the underlying child process.

## 2.13.2 - PushResult to expose all non-empty remote messages

- Further to `2.13.0` includes all (non-empty) `remote:` lines in the `PushResult`,
  including `remote:` lines used for other parser results (ie: `pullRequestUrl` etc).

## 2.13.1 - Add support for parsing GitLab Pull Request Url Message

- Further to `2.13.0` adding support for parsing the reponse to `git.push`, adds support for the pull request message
  used by gitlab.

## 2.13.0 - Upgraded Pull & Merge and parser for Push  

- `.push` and `.pushTags` rewritten as v2 style tasks. The git response is now parsed and returned as a
  [PushResult](./typings/response.d.ts)

- Pull and merge rewritten to fit the TypeScript tasks style. 

- Integration tests updated to run through jest directly without compiling from nodeunit

## 2.12.0 - Bug fix: chaining onto / async awaiting `git.tags` failed

- resolves an issue whereby the `git.tags` method could not be chained or used as an async/promise.

## 2.11.0 - Parallel / concurrent tasks, fresh repo status parser & bug-fix in `checkoutLocalBranch`

- until now, `simple-git` reject all pending tasks in the queue when a task has failed. From `2.11.0`, only
  tasks chained from the failing one will be rejected, other tasks can continue to be processed as normal,
  giving the developer more control over which tasks should be treated as atomic chains, and which can be
  [run in parallel](./readme.md#concurrent--parallel-requests).
  
  To support this, and to prevent the issues seen when `git` is run concurrently in too many child processes,
  `simple-git` will limit the number of tasks running in parallel at any one time to be at most 1 from each
  chain (ie: chained tasks are still run in series) and at most 5 tasks across all chains (
  [configurable](./readme.md#configuration) by passing `{maxConcurrentProcesses: x}` in the `simpleGit` constructor). 

- add support to `git.status()` for parsing the response of a repo that has no commits yet, previously
  it wouldn't determine the branch name correctly.

- resolved a flaw introduced in `2.9.0` whereby `checkoutLocalBranch` would silently fail and not check out the branch 

## 2.10.0 - trailing options in checkout, init, status, reset & bug-fix awaiting a non-task

- `git.checkout` now supports both object and array forms of supplying trailing options.

```typescript
import simpleGit from 'simple-git';
await simpleGit().checkout('branch-name', ['--track', 'remote/branch']);
await simpleGit().checkout(['branch-name', '--track', 'remote/branch']);
await simpleGit().checkout({'branch-name': null});
```

- `git.init` now supports both object and array forms of supplying trailing options and now
  parses the response to return an [InitResult](./typings/response.d.ts);

```typescript
import simpleGit, { InitResult } from 'simple-git';
const notSharedInit: InitResult = await simpleGit().init(false, ['--shared=false']);
const notSharedBareInit: InitResult = await simpleGit().init(['--bare', '--shared=false']);
const sharedInit: InitResult = await simpleGit().init(false, {'--shared': 'true'});
const sharedBareInit: InitResult = await simpleGit().init({'--bare': null, '--shared': 'false'});
```

- `git.status` now supports both object and array forms of supplying trailing options.

```typescript
import simpleGit, { StatusResult } from 'simple-git';
const repoStatus: StatusResult = await simpleGit().status();
const subDirStatus: StatusResult = await simpleGit().status(['--', 'sub-dir']);
```

- `git.reset` upgraded to the new task style and exports an enum `ResetMode` with all supported
  merge modes and now supports both object and array forms of supplying trailing options.

```typescript
import simpleGit, { ResetMode } from 'simple-git';

// git reset --hard
await simpleGit().reset(ResetMode.HARD);

// git reset --soft -- sub-dir
await simpleGit().reset(ResetMode.SOFT, ['--', 'sub-dir']);
```

- bug-fix: it should not be possible to await the `simpleGit()` task runner, only the tasks it returns.

```typescript
expect(simpleGit().then).toBeUndefined();
expect(simpleGit().init().then).toBe(expect.any(Function));
```

## 2.9.0 - checkIsRepo, rev-parse 

- `.checkIsRepo()` updated to allow choosing the type of check to run, either by using the exported `CheckRepoActions` enum
  or the text equivalents ('bare', 'root' or 'tree'):
  - `checkIsRepo(CheckRepoActions.BARE): Promise<boolean>` determines whether the working directory represents a bare repo.
  - `checkIsRepo(CheckRepoActions.IS_REPO_ROOT): Promise<boolean>` determines whether the working directory is at the root of a repo.
  - `checkIsRepo(CheckRepoActions.IN_TREE): Promise<boolean>` determines whether the working directory is a descendent of a git root.

- `.revparse()` converted to a new style task

## 2.8.0 - Support for `default` import in TS without use of `esModuleInterop`

- Enables support for using the default export of `simple-git` as an es module, in TypeScript it is no
  longer necessary to enable the `esModuleInterop` flag in the `tsconfig.json` to consume the default
  export.

### 2.7.2 - Bug Fix: Remove `promise.ts` source from `simple-git` published artifact

- Closes #471, whereby the source for the promise wrapped runner would be included in the published artifact
  due to sharing the same name as the explicitly included `promise.js` in the project root. 

### 2.7.1 - Bug Fix: `await git.log` having imported from root `simple-git`

- Fixes #464, whereby using `await` on `git.log` without having supplied a callback would ignore the leading options
  object or options array. 

## 2.7.0 - Output Handler and logging

- Updated to the `outputHandler` type to add a trailing argument for the arguments passed into the child process.
- All logging now uses the [debug](https://www.npmjs.com/package/debug) library. Enable logging by adding `simple-git`
  to the `DEBUG` environment variable. `git.silent(false)` can still be used to explicitly enable logging and is
  equivalent to calling `require('debug').enable('simple-git')`. 

## 2.6.0 - Native Promises, Typed Errors, TypeScript Importing, Git.clean and Git.raw

### Native Promises

- _TL;DR - `.then` and `.catch` can now be called on the standard `simpleGit` chain to handle the promise
  returned by the most recently added task... essentially, promises now just work the way you would expect
  them to._
- The main export from `simple-git` no longer shows the deprecation notice for using the
  `.then` function, it now exposes the promise chain generated from the most recently run
  task, allowing the combination of chain building and ad-hoc splitting off to a new promise chain.
  - See the [unit](./test/unit/promises.spec.js) and [integration](./test/integration/promise-from-root.spec.js) tests.
  - See the [typescript consumer](./test/consumer/ts-default-from-root.spec.ts) test.

### TypeScript Importing

- Promise / async interface and TypeScript types all available from the `simple-git` import rather than needing
  `simple-git/promise`, see examples in the [ReadMe](./readme.md) or in the [consumer tests](./test/consumer).

### Typed Errors

- Tasks that previously validated their usage and rejected with a `TypeError` will now reject with a
 [`TaskConfigurationError`](./src/lib/errors/task-configuration-error.ts).

- Tasks that previously rejected with a custom object (currently only `git.merge` when the auto-merge fails)
  will now reject with a [`GitResponseError`](./src/lib/errors/git-response-error.ts) where previously it
  was a modified `Error`.

### Git Clean

- `git.clean(...)` will now return a `CleanSummary` instead of the raw string data

### Git Raw

- `git.raw(...)` now accepts any number of leading string arguments as an alternative to the
  single array of strings.

## 2.5.0 - Git.remote

- all `git.remote` related functions converted to TypeScript

## 2.4.0 - Git.subModule

- all `git.subModule` related functions converted to TypeScript

## 2.3.0 - Git.config

- add new `git.listConfig` to get current configuration
- `git.addConfig` supports a new `append` flag to append the value into the config rather than overwrite existing

## 2.2.0 - Git.branch

- all `git.branch` related functions converted to TypeScript
- add new `git.deleteLocalBranches` to delete multiple branches in one call
- `git.deleteLocalBranches` and `git.deleteLocalBranch` now support an optional `forceDelete` flag

## 2.1.0 - Git.tag

- `.tags`, `.addTag` and `.addAnnotatedTag` converted to TypeScript, no backward compatibility changes

## 2.0.0 - Incremental switch to TypeScript and rewritten task execution

- If your application depended on any functions with a name starting with an `_`, the upgrade may not be seamless,
please only use the documented public API.

- `git.log` date format is now strict ISO by default (ie: uses the placeholder `%aI`) instead of the 1.x default of
`%ai` for an "ISO-like" date format. To restore the old behaviour, add `strictDate = false` to the options passed to
`git.log`. 
 

## 1.110.0 - ListLogLine

- The default format expression used in `.log` splits ref data out of the `message` into a property of its own:  `{ message: 'Some commit message (some-branch-name)' }` becomes `{ message: 'Some commit message', refs: 'some-branch-name' }` |
- The commit body content is now included in the default format expression and can be used to identify the content of merge conflicts eg: `{ body: '# Conflicts:\n# some-file.txt' }` | 


## 1.0.0

Bumped to a new major revision in the 1.x branch, now uses `ChildProcess.spawn` in place of `ChildProcess.exec` to
add escaping to the arguments passed to each of the tasks.

