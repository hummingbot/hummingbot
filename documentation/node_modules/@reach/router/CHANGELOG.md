## v1.3.4

- d7e4cfc Support forwarding url params with wildcard paths

## v1.3.3

_1.3.2 was a failed publish_

- 8b93694 Fix an encoding issue with browsers who do not encode urls
- d0962d7 Fix a bug on specific vendors that do not ship `location.pathname`
- 244e2bf Improve compatibility for `createMemorySource`

## v1.3.1

- f40ea53 Fix an accidental breaking change not exposing all location properties

## v1.3.0

- 56d4dca Added 4 new Hook APIs!
  - `useLocation`
  - `useParams`
  - `useNavigate`
  - `useMatch`
- 15298df Improved displayName for react context
- 11e9ed6 Fixed a bug that pushed to history when a user clicks the same path
- ccfc3c8 Added support for trailing wildcard names e.g., `path="/files/*filePath"`
- ad52cd3 Upgraded create-react-context to an MIT license compatible version
- 0a8af93 Fixed a bug with checking own property on locations
- 28a79e7 Fixed `search` not being prepended with a `?`
- 77fa233 Added displayName to Link

## v1.2.1

- 1f9f908 replace unstable_deferredUpdates with rAF

## v1.2.0

- a7a1c84 fixed focus being stolen from [autofocus] elements
- 8a56262 Added `hash` and `search` to server location
- 1c13f8a Added history "PUSH" and "POP" actions to listener callback
- 534f67c Added globalHistory to index exports
- 8cb6e83 allow falsey children in Router

## v1.1.1

- e0338b5c Removed vestigial dependencies from package.json
- fix/automated linting

## v1.1.0

- 53f06958 Added ref forwarding and `innerRef` fallback

## v1.0.0

- Added literally everything.
