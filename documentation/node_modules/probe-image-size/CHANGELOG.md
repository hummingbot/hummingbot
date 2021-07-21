# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [5.0.0] - 2019-09-14
### Changed
- Drop `any-promise`, use native, #32.


## [4.1.1] - 2019-07-11
### Fixed
- Fix streams unpipe (after 4.1.0 changes), #34.


## [4.1.0] - 2019-07-09
### Changed
- Deps bump.
- Update Travis-CI node versions to actual.

### Fixed
- Fix content ungzip from misconfigured servers, #31.


## [4.0.1] - 2019-07-08
### Fixed
- Fix regexp to ignore SVG `stroke-width` attr, #33.


## [4.0.0] - 2018-03-05
### Changed
- Roll back `got` -> `request`, see #16.
- Default timeout 30s -> 60s.

### Fixed
- Fix padding parse in jpeg, #20.


## [3.2.0] - 2017-11-22
### Changed
- Roll back `got` to 6.x due serious regressions, see #16.
  Next attempt will be switching to `request` and releasing 4.0.0.


## [3.1.0] - 2017-06-08
### Changed
- Maintenance, deps bump. `got` 6.x -> 7.x. `got` timeouts may work a bit
  different but should affect result.


## [3.0.0] - 2016-12-02
### Changed
- Rewrite internals to `Promise`.
- Separate options from url for http probe (old signature still supported
  for compatibility).
- `err.status` -> `err.statusCode`
- remove `{ rejectUnauthorized: false }` from defaults.
- User-Agent string update.
- Replaced `request` dependency with `got` (read options description in doc).
- Retry requests on network fail.
- Switched from `readable-stream` to native `stream` (node 4+ has normal Stream3).
- Proper class for errors.


## [2.2.0] - 2016-10-26
### Added
- Add `.url` with actual image address (after redirects) for remotes.


## [2.1.1] - 2016-08-25
### Added
- Add default user agent to http requests (if not set by options), #8.


## [2.1.0] - 2016-07-14
### Changed
- Internal parsers api cleanup - switch from callbacks to events.

### Fixed
- Fixed "write after end" error under heavy load.


## [2.0.1] - 2016-07-01
### Fixed
- Fixed bug in streams cleanup condition.


## [2.0.0] - 2016-06-25
### Added
- SVG support
- Return dimention units ('px' everywhere except SVG)
### Changed
- width/height now can be float (with fractional part)


## [1.2.1] - 2016-05-30
### Fixed
- Stream: posponed callback to avoid possible races on forced stream close.


## [1.2.0] - 2016-05-28
### Added
- Added `.sync.probe()` method.
- 100% tests coverage.

### Changed
- Splited to separate files (simplify browserification).
- Faster return on positive result & faster resource release.

### Fixed
- Fix stream error handling.


## [1.1.0] - 2016-05-25
### Added
- Added promise support.

### Changed
- Use `readable-stream` instead of `stream`.
- Reorganised internal files structure & tests.


## [1.0.6] - 2016-04-13
### Fixed
- Fixed parser crashes on zero length data & offsets.


## [1.0.5] - 2015-12-15
### Changed
- Increased http request timeout to 30 seconds.
- Don't check SSL sertificates.


## [1.0.4] - 2015-09-22
### Fixed
- Fixed crash on empty JPEG markers.


## [1.0.3] - 2015-09-19
### Fixed
- Fixed catch internal exceptions from `request`.


## [1.0.2] - 2015-09-16
### Added
- Added `ECONTENT` error code for parse errors.


## [1.0.1] - 2015-09-14
### Added
- Return image length when possible.
- Support URLs in dev helper script.


## [1.0.0] - 2015-09-12
### Added
- First release.


[5.0.0]: https://github.com/nodeca/probe-image-size/compare/4.1.1...5.0.0
[4.1.1]: https://github.com/nodeca/probe-image-size/compare/4.1.0...4.1.1
[4.1.0]: https://github.com/nodeca/probe-image-size/compare/4.0.1...4.1.0
[4.0.1]: https://github.com/nodeca/probe-image-size/compare/4.0.0...4.0.1
[4.0.0]: https://github.com/nodeca/probe-image-size/compare/3.2.0...4.0.0
[3.2.0]: https://github.com/nodeca/probe-image-size/compare/3.1.0...3.2.0
[3.1.0]: https://github.com/nodeca/probe-image-size/compare/3.0.0...3.1.0
[3.0.0]: https://github.com/nodeca/probe-image-size/compare/2.2.0...3.0.0
[2.2.0]: https://github.com/nodeca/probe-image-size/compare/2.1.1...2.2.0
[2.1.1]: https://github.com/nodeca/probe-image-size/compare/2.1.0...2.1.1
[2.1.0]: https://github.com/nodeca/probe-image-size/compare/2.0.1...2.1.0
[2.0.1]: https://github.com/nodeca/probe-image-size/compare/2.0.0...2.0.1
[2.0.0]: https://github.com/nodeca/probe-image-size/compare/1.2.1...2.0.0
[1.2.1]: https://github.com/nodeca/probe-image-size/compare/1.2.0...1.2.1
[1.2.0]: https://github.com/nodeca/probe-image-size/compare/1.1.0...1.2.0
[1.1.0]: https://github.com/nodeca/probe-image-size/compare/1.0.6...1.1.0
[1.0.6]: https://github.com/nodeca/probe-image-size/compare/1.0.5...1.0.6
[1.0.5]: https://github.com/nodeca/probe-image-size/compare/1.0.4...1.0.5
[1.0.4]: https://github.com/nodeca/probe-image-size/compare/1.0.3...1.0.4
[1.0.3]: https://github.com/nodeca/probe-image-size/compare/1.0.2...1.0.3
[1.0.2]: https://github.com/nodeca/probe-image-size/compare/1.0.1...1.0.2
[1.0.1]: https://github.com/nodeca/probe-image-size/compare/1.0.0...1.0.1
[1.0.0]: https://github.com/nodeca/probe-image-size/releases/tag/1.0.0
