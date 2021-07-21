## [8.2.5] 2018-12-12

### Fixed

- Whitelist package.json files.

## [8.2.4] 2018-12-12

### Added

- A CHANGELOG.md file, see
[#78](https://github.com/jorangreef/sudo-prompt/issues/78).

## [8.2.3] 2018-09-11

### Fixed

- README: Link to concurrency discussion.

## [8.2.2] 2018-09-11

### Fixed

- README: Details on concurrency.

## [8.2.1] 2018-09-11

### Fixed

- A rare idempotency edge case where a command might have been run more than
once, given a very specific OS environment setup.

## [8.2.0] 2018-03-22

### Added

- Windows: Fix `cd` when `cwd` is on another drive, see
[#70](https://github.com/jorangreef/sudo-prompt/issues/70).

## [8.1.0] 2018-01-10

### Added

- Linux: Increase `maxBuffer` limit to 128 MiB, see
[#66](https://github.com/jorangreef/sudo-prompt/issues/66).

## [8.0.0] 2018-11-02

### Changed

- Windows: Set code page of command batch script to UTF-8.

## [7.1.1] 2017-07-18

### Fixed

- README: Explicitly mention that no child process is returned.

## [7.0.0] 2017-03-15

### Changed

- Add status code to errors on Windows and macOS.

## [6.2.1] 2016-12-16

### Fixed

- README: Syntax highlighting.

## [6.2.0] 2016-08-17

### Fixed

- README: Rename OS X to macOS.

## [6.1.0] 2016-08-02

### Added

- Yield an error if no polkit authentication agent is found, see
[#29](https://github.com/jorangreef/sudo-prompt/issues/29).

## [6.0.2] 2016-07-21

### Fixed

- README: Update explanation of Linux behavior.

## [6.0.1] 2016-07-15

### Fixed

- Update keywords in package.json.

## [6.0.0] 2016-07-15

### Changed

- Add support for Windows.
