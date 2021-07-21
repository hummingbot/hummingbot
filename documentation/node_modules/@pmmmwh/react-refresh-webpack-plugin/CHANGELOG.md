## 0.4.2 (3 September 2020)

### Fixes

- Patched loader to use with Node.js global `fetch` polyfills (#193)
- Patched default `include` and `exclude` options to be case-insensitive (#194)

## 0.4.1 (28 July 2020)

### Fixes

- Fixed accidental use of testing alias `webpack.next` in published plugin code (#167)

## 0.4.0 (28 July 2020)

### BREAKING

- Minimum required Node.js version have been bumped to 10 as Node.js 8 is EOL now.
- Minimum required Webpack version is now `v4.43.0` or later as we adopted the new `module.hot.invalidate` API (#).
  The new API enabled us to bail out of the HMR loop less frequently and provide a better experience.
  If you really cannot upgrade, you can stay on `0.3.3` for the time being.
- While most of our public API did not change, this release is closer to a rewrite than a refactor.
  A lot of files have moved to provide easier access to files for advanced users and frameworks (#122).
  You can check the difference in the PR to see what have moved and where they are now.
- The `useLegacyWDSSockets` option is now scoped under the `overlay` option (#153).

### Features

- Adopted the `module.hot.invalidate()` API, which means we will now bail out less often (#89)
- Attach runtime on Webpack's global scope instead of `window`, making the plugin platform-agnostic (#102)
- Added stable support for **Webpack 5** and beta support for **Module Federation** (#123, #132, #164)
- Socket integration URL detection via `document.currentScript` (#133)
- Relaxed requirements for "required" `overlay` options to receive `false` as value (#154)
- Prefixed all errors thrown by the plugin (#161)
- Eliminated use of soon-to-be-deprecated `lodash.debounce` package (#163)

### Fixes

- Fixed circular references for `__react_refresh_error_overlay__` and `__react_refresh_utils` (#116)
- Fixed IE11 compatibility (#106, #121)
- Rearranged directories to provide more ergonomic imports (#122)
- Fixed issues with Babel/ESLint/Flow regarding loader ordering and runtime cleanup (#129, #140)
- Correctly detecting the HMR plugin (#130, #160)
- Fixed unwanted injection of error overlay in non-browser environment (#146)
- Scoped the `useLegacyWDSSockets` options under `overlay` to reflect its true use (#153)
- Fixed non-preserved relative ordering of Webpack entries (#165)

### Internal

- Full HMR test suite - we are confident the plugin works! (#93, #96)
- Unit tests for all plugin-related Node.js code (#127)

## 0.3.3 (29 May 2020)

### Fixes

- Removed unrecoverable React errors check and its corresponding bail out logic on hot dispose (#104)

## 0.3.2 (22 May 2020)

### Fixes

- Fixed error in overlay when stack trace is unavailable (#91)
- Fixed IE11 compatibility (#98)

## 0.3.1 (11 May 2020)

### Fixes

- Relaxed peer dependency requirements for `webpack-plugin-serve`

## 0.3.0 (10 May 2020)

### BREAKING

- Deprecated the `disableRefreshCheck` flag (#60)

### Features

- Added custom error overlay support (#44)
- Added example project to use TypeScript without usual Babel settings (#46)
- Added custom socket parameters for WDS (#52)
- Added TypeScript definition files (#65)
- Added stricter options validation rules (#62)
- Added option to configure socket runtime to support more hot integrations (#64)
- Added support for `webpack-plugin-serve` (#74)

### Fixes

- Fixed non-dismissible overlay for build warnings (#57)
- Fixed electron compatibility (#58)
- Fixed optional peer dependencies to be truly optional (#59)
- Fixed compatibility issues caused by `node-url` (#61)
- Removed check for `react` import for compatibility (#69)

## 0.2.0 (2 March 2020)

### Features

- Added `webpack-hot-middleware` support (#23)

### Fixes

- Fixed dependency on a global `this` variable to better support web workers (#29)

## 0.1.3 (19 December 2019)

### Fixes

- Fixed runtime template injection when the `runtimeChunks` optimization is used in Webpack (#26)

## 0.1.2 (18 December 2019)

### Fixes

- Fixed caching of Webpack loader to significantly improve performance (#22)

## 0.1.1 (13 December 2019)

### Fixes

- Fixed usage of WDS SockJS fallback (#17)

## 0.1.0 (7 December 2019)

- Initial public release
