# Changelog

All notable changes to this project will be documented in this file. See [standard-version](https://github.com/conventional-changelog/standard-version) for commit guidelines.

## [2.0.0](https://gitlab.com/m03geek/node-object-hash/compare/v2.0.0-rc.1...v2.0.0) (2019-09-07)

## [2.0.0-rc.1](https://gitlab.com/m03geek/node-object-hash/compare/v2.0.0-rc.0...v2.0.0-rc.1) (2019-09-03)

## [2.0.0-rc.0](https://gitlab.com/m03geek/node-object-hash/compare/v1.4.2...v2.0.0-rc.0) (2019-09-03)


### ⚠ BREAKING CHANGES

* Library rewritten in typescript that could cause some side-effects, but it should not.
* With `coerce=false` `Set`s will no longer generate the same hashes as `Array`s. In order to restore previous behavior set `coerce.set=true`.
* With `coerce=false` `Symbol`s will generate hash based on symbol `.toString` value. That's useful for `Symbol.for('smth')`. If `coerce.symbol=true` all `Symbols`s will have equal hashes. 
TLDR; If you use library with `Set`s or `Symbol`s with `coerce=false` in order to keep hashes the same as in `v1.X.X` you should use following constructor:
```
const hasher = require('node-object-hash')({coerce: {set: true, symbol: true}})
```
* Object sorter sources moved to `dist` directory. If you required it directly via `require('node-object-hash/objectSorter')` you should change it to require('node-object-hash/dist/objectSorter').
* Removed old `v0` version from code.
* Changed license to MIT.

### Bug Fixes

* **hasher:** fix options ([05241ca](https://gitlab.com/m03geek/node-object-hash/commit/05241ca))

### Features

* major refactor ([450471e](https://gitlab.com/m03geek/node-object-hash/commit/450471e))
* New granular options. Now you can specify what types need to be sorted or coerced.
* Add new `trim` option. It can be used to remove unncecessary spaces in `string`s or `function` bodies.
* Library rewritten to typescript, so it may have better ts compatibility.

## [1.4.X](https://gitlab.com/m03geek/node-object-hash/compare/v1.3.0...v1.4.2)

### Features 

* Add support for objects without constructor #11 [PR @futpib](https://gitlab.com/m03geek/node-object-hash/pull/12)
* Simplify eslint rules, update codestyle

### Fixes

* Fix npm links issues in readme
* Update dev dependencies

## [1.3.X](https://gitlab.com/m03geek/node-object-hash/compare/v1.2.0...v1.3.0)

### Features

* Add definition types to support typescript
* Add >=node-8.0.0 support in tests.

## [1.2.X](https://gitlab.com/m03geek/node-object-hash/compare/v1.1.6...v1.2.0)

### Features 

- Added typed arrays support
- Added primitive type constructors support
- Add more docs about type mapping and type coercion

## [1.1.X](https://gitlab.com/m03geek/node-object-hash/compare/v1.0.3..v1.1.6)

### Features

Mainly all changes affected codestyle and documentation to provide better
experience using this library. There are no changes that should affect
functionality.

- Renamed `sortObject` function to `sort` (old one is still present in code
for backward compatibility).
- Performed some refactoring for better codestyle and documentation.
- Old version (`0.X.X`) moved to subfolder (`./v0`).
- Advanced API reference added: [link](API.md).

## [1.0.0](https://gitlab.com/m03geek/node-object-hash/compare/v0.1.0...v1.0.3)

- Sorting mechanism rewritten form ES6 Maps to simple arrays
 (add <=node-4.0.0 support)
- Performance optimization (~2 times faster than 0.x.x)
- API changes:
  - Now module returns 'constructor' function, where you can set
  default parameters: ```var objectHash = require('node-object-hash')(options);```

In case if you still need an old 0.x.x version it's available in `hash.js`
file.
