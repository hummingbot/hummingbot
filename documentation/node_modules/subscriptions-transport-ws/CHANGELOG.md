# Changelog

## v0.9.18 (2020-08-17)

### Bug Fixes

- Do not send GQL_STOP when unsubscribing after GQL_COMPLETE is received.  <br/>
  [@onhate](https://github.com/onhate) in [#775](https://github.com/apollographql/subscriptions-transport-ws/pull/775)
- Clear WebSocket event listeners on close.  <br/>
  [@tretne](https://github.com/tretne) in [#615](https://github.com/apollographql/subscriptions-transport-ws/pull/615)
- Fix `MessageTypes` TS import errors.  <br/>
  [@sneko](https://github.com/sneko) in [#412](https://github.com/apollographql/subscriptions-transport-ws/issues/412)
- Ensure `promisedParams` errors are not handled twice.  <br/>
  [@benjie](https://github.com/benjie) in [#514](https://github.com/apollographql/subscriptions-transport-ws/pull/514)
- Fix invalid `formatResponse` console error.  <br/>
  [@renatorib](https://github.com/renatorib) in [#761](https://github.com/apollographql/subscriptions-transport-ws/pull/761)
- Destructure the correct error object in `MessageTypes.GQL_START`.  <br/>
  [@gregbty](https://github.com/gregbty) in [#588](https://github.com/apollographql/subscriptions-transport-ws/pull/588)
- Inline source in sourcemap files to fix broken source lookups.  <br/>
  [@alexkirsz](https://github.com/alexkirsz) in [#513](https://github.com/apollographql/subscriptions-transport-ws/pull/513)

### New Features

- Add `minTimeout` option for client.  <br/>
  [@jedwards1211](https://github.com/jedwards1211) in [#675](https://github.com/apollographql/subscriptions-transport-ws/pull/675)
- Accept extra WebSocket client arguments.  <br/>
  [@GingerBear](https://github.com/GingerBear) in [#561](https://github.com/apollographql/subscriptions-transport-ws/pull/561)
- Support server-defined payload in GQL_CONNECTION_ACK message.  <br/>
  [@mattkrick](https://github.com/mattkrick) in [#347](https://github.com/apollographql/subscriptions-transport-ws/pull/347)

## v0.9.17

- Bump `graphql` peer/dev deps.  <br/>
  [@hwillson](https://github.com/hwillson) in [#778](https://github.com/apollographql/subscriptions-transport-ws/pull/778)

## v0.9.16
- Add ability to set custom WebSocket protocols for client. <br/>
  [@pkosiec](https://github.com/pkosiec) in [#477](https://github.com/apollographql/subscriptions-transport-ws/pull/477)

## v0.9.15

- Add support for `graphql` and `@types/graphql` 14.  <br/>
  [@caiquecastro](https://github.com/caiquecastro) in [#464](https://github.com/apollographql/subscriptions-transport-ws/pull/464)

## v0.9.14
- Allow dynamically specifying/overriding the schema in the object returned from `onOperation` [PR #447](https://github.com/apollographql/subscriptions-transport-ws/pull/447)

## v0.9.13
- Allow connectionParams to be a Promise [PR #443](https://github.com/apollographql/subscriptions-transport-ws/pull/443)

## v0.9.12
- use lightweight lodash alternatives [Issue #430](https://github.com/apollographql/subscriptions-transport-ws/issues/430)
- applies fix suggested by @pandemosth regarding "No subscription is made on reconnect" and "Duplicate subscription made on reconnect" described in [Issue #295](https://github.com/apollographql/subscriptions-transport-ws/issues/295#issuecomment-398184429)

## v0.9.11
- allow using custom WebSocket server implementation [PR #374](https://github.com/apollographql/subscriptions-transport-ws/pull/374)

## v0.9.10
- upgrade ws and eventemitter3

## v0.9.9
- fix issue with @types/graphql@0.13

## v0.9.8
- added `error` event to handle connection errors and debug network troubles [PR #341](https://github.com/apollographql/subscriptions-transport-ws/pull/341).
- added feature inactivityTimeout [PR #390](https://github.com/apollographql/subscriptions-transport-ws/pull/390)

## v0.9.7
- change default timeout from 10s to 30s [PR #368](https://github.com/apollographql/subscriptions-transport-ws/pull/368)
- pass `request` (`upgradeReq`) to `ConnectionContext` [PR #369](https://github.com/apollographql/subscriptions-transport-ws/pull/369)
- pass `ConnectionContext` to `onDisconnect()` as second argument [PR #369](https://github.com/apollographql/subscriptions-transport-ws/pull/369)

## v0.9.6
- fix shallow cloning on contexts which are classes
- upgrade to support graphql 0.13.X
- bump iterall version [PR #362](https://github.com/apollographql/subscriptions-transport-ws/pull/362)

## v0.9.5
- docs(setup): Fix dead link to subscriptions-to-schema
- upgrade to support graphql 0.12.X

## v0.9.4
- fix unhandledRejection error in GQL_START handling if initPromise rejected [PR #310](https://github.com/apollographql/subscriptions-transport-ws/pull/310)

## v0.9.3
- fix unhandledRejection error in GQL_STOP handling if initPromise rejected [PR #309](https://github.com/apollographql/subscriptions-transport-ws/pull/309)
- fix return of init error message to legacy clients [PR #309](https://github.com/apollographql/subscriptions-transport-ws/pull/309)

## v0.9.2
- fix format of keep alive message sent to legacy clients. [PR #297](https://github.com/apollographql/subscriptions-transport-ws/pull/297)
- fix(isPromise): Made checks for promises in server.ts loose to allow for augmented and polyfilled promises. [PR #304](https://github.com/apollographql/subscriptions-transport-ws/pull/304)

## v0.9.1
- docs(KEEP_ALIVE): Updated protocol docs to explain the correct server implementation of `GQL_CONNECTION_INIT`, `GQL_CONNECTION_ACK` and `GQL_CONNECTION_KEEP_ALIVE` [PR #279](https://github.com/apollographql/subscriptions-transport-ws/pull/279)
- docs(language-typos): Update documentation to remove some language typos [PR #282](https://github.com/apollographql/subscriptions-transport-ws/pull/282)
- fix(typescript-2.5.x-typings): Fix a couple of typing changes required by latest typing files with TypeScript 2.5.X. [PR #285](https://github.com/apollographql/subscriptions-transport-ws/pull/285)
- test(NA): fixed run condition on tests for gql_data with errors [PR #289](https://github.com/apollographql/subscriptions-transport-ws/pull/289)

## v0.9.0
- docs(README): Fix example for subscribe and subscribeToMore [PR #273](https://github.com/apollographql/subscriptions-transport-ws/pull/273)
- Add support for GraphQL 0.11.0 [PR #261](https://github.com/apollographql/subscriptions-transport-ws/pull/261)
- **BREAKING CHANGE**: Remove support for Subscription Manager [PR #261](https://github.com/apollographql/subscriptions-transport-ws/pull/261)
- **BREAKING CHANGE**: Remove support for all deprecated API [PR #272](https://github.com/apollographql/subscriptions-transport-ws/pull/272)

## v0.8.3
- docs(README): Fix options example for subscribe methods [PR #266](https://github.com/apollographql/subscriptions-transport-ws/pull/266)
- Gracefully unsubscribe to all pending operations before a requested close by the user  [PR #245](https://github.com/apollographql/subscriptions-transport-ws/pull/245)
- Add `close` method to server [PR #257](https://github.com/apollographql/subscriptions-transport-ws/pull/257)
- Bugfix: Observer callbacks should be optional [PR #256](https://github.com/apollographql/subscriptions-transport-ws/pull/256)

## v0.8.2
- Add request interface as a preparation for Apollo 2.0 [PR #242](https://github.com/apollographql/subscriptions-transport-ws/pull/242)
- Add Validation step to server [PR #241](https://github.com/apollographql/subscriptions-transport-ws/pull/241)
- Call operation handler before delete the operation on operation complete [PR #239](https://github.com/apollographql/subscriptions-transport-ws/pull/239)

## v0.8.1
- Send first keep alive message right after the ack [PR #223](https://github.com/apollographql/subscriptions-transport-ws/pull/223)
- Return after first post-install when it should install dev dependencies [PR #218](https://github.com/apollographql/subscriptions-transport-ws/pull/218)
- On installing from branch install dev dependencies only if dist folder isn't found [PR #219](https://github.com/apollographql/subscriptions-transport-ws/pull/219)

## v0.8.0
- Expose opId `onOperationComplete` method [PR #211](https://github.com/apollographql/subscriptions-transport-ws/pull/211)
- Fix to make library able to be installed from a branch [PR #208](https://github.com/apollographql/subscriptions-transport-ws/pull/208)
- Fix for non forced closes (now it wont send connection_terminate) [PR #197](https://github.com/apollographql/subscriptions-transport-ws/pull/197)
- A lot of connection's flow improvements (on connect, on disconnect and on reconnect) [PR #197](https://github.com/apollographql/subscriptions-transport-ws/pull/197)
- Require specific lodash/assign module instead of entire package, so memory impact is reduced [PR #196](https://github.com/apollographql/subscriptions-transport-ws/pull/196)
- docs(README): Fix onEvent(eventName, callback, thisContext) list of eventName [PR #205](https://github.com/apollographql/subscriptions-transport-ws/pull/205)

## v0.7.3
- Fix for first subscription is never unsubscribed [PR #179](https://github.com/apollographql/subscriptions-transport-ws/pull/179)

## v0.7.2
- Increase default keep-alive timeout to 30s [PR #177](https://github.com/apollographql/subscriptions-transport-ws/pull/177)
- Operation key is now `string` instead of `number` [PR #176](https://github.com/apollographql/subscriptions-transport-ws/pull/176)

## v0.7.1
- Fix for reconnect after manual close [PR #164](https://github.com/apollographql/subscriptions-transport-ws/pull/164)
- test(disconnect): added tests for client-server flow for unsubscribe and disconnect [PR #163](https://github.com/apollographql/subscriptions-transport-ws/pull/163)
- Various dependencies updates [PR #152](https://github.com/apollographql/subscriptions-transport-ws/pull/152) [PR #162](https://github.com/apollographql/subscriptions-transport-ws/pull/162)
- docs(README): fix docs [PR #151](https://github.com/apollographql/subscriptions-transport-ws/pull/151)

## v0.7.0
- Client exposes new asyncronous middleware to modify `OperationOptions` [PR #78](https://github.com/apollographql/subscriptions-transport-ws/pull/78)
- Added `WebSocketServer` error handler to prevent uncaught exceptions. Fixes [Issue #94](https://github.com/apollographql/subscriptions-transport-ws/issues/94)
- Updated `ws` dependency to the lastest.
- Introduce lazy mode for connection, and accept function as `connectionParams` [PR #131](https://github.com/apollographql/subscriptions-transport-ws/pull/131)
- Extend transport protocol to support GraphQL queries and mutations over WebSocket [PR #108](https://github.com/apollographql/subscriptions-transport-ws/pull/108)
- Added built-in support for `subscribe` from `graphql-js` [PR #133](https://github.com/apollographql/subscriptions-transport-ws/pull/133)
- Fixed infinity reconnects when server accepts connections but its in an error state. [PR #135](https://github.com/apollographql/subscriptions-transport-ws/pull/135)
- Force close client-side socket when using `close()`, and ignore reconnect logic. [PR #137](https://github.com/apollographql/subscriptions-transport-ws/pull/137)
- Added new connection events to give a more accurate control over the connection state [PR #139](https://github.com/apollographql/subscriptions-transport-ws/pull/139). Fixes [Issue #136](https://github.com/apollographql/subscriptions-transport-ws/issues/136).
- Replaced `Object.assign` by `lodash.assign` to extend browser support [PR #144](https://github.com/apollographql/subscriptions-transport-ws/pull/144). Fixes [Issue #141](https://github.com/apollographql/subscriptions-transport-ws/issues/141)

## v0.6.0

- Enabled Greenkeeper and updated dependencies, includes major version bump of ws [PR #90](https://github.com/apollographql/subscriptions-transport-ws/pull/90)

## v0.6.0
- Protocol update to support queries, mutations and also subscriptions. [PR #108](https://github.com/apollographql/subscriptions-transport-ws/pull/108)
- Added support in the server for GraphQL Executor. [PR #108](https://github.com/apollographql/subscriptions-transport-ws/pull/108)
- Added support in the server executor for `graphql-js subscribe`. [PR #846](https://github.com/graphql/graphql-js/pull/846)

## v0.5.5
- Remove dependency on `graphql-tag/printer` per [graphql-tag#54](https://github.com/apollographql/graphql-tag/issues/54) [PR #98](https://github.com/apollographql/subscriptions-transport-ws/pull/98)

## v0.5.4
- Ensure INIT is sent before SUBSCRIPTION_START even when client reconnects [PR #85](https://github.com/apollographql/subscriptions-transport-ws/pull/85)
- Allow data and errors in payload of SUBSCRIPTION_DATA [PR #84](https://github.com/apollographql/subscriptions-transport-ws/pull/84)
- Expose `index.js` as entrypoint for server/NodeJS application to allow NodeJS clients to use `SubscriptionClient` [PR #91](https://github.com/apollographql/subscriptions-transport-ws/pull/91)
- Fixed a bug with missing error message on `INIT_FAIL` message [#88](https://github.com/apollographql/subscriptions-transport-ws/issues/88)

## v0.5.3
- Fixed a bug with `browser` declaration on package.json ([Issue #79](https://github.com/apollographql/subscriptions-transport-ws/issues/79))

## v0.5.2
- Updated dependencies versions
- Fixed typings issue with missing `index.d.ts` file. [PR #73](https://github.com/apollographql/subscriptions-transport-ws/pull/73)
- Transpiling client.js to target browsers using webpack. [PR #77](https://github.com/apollographql/subscriptions-transport-ws/pull/77)

## v0.5.1
- Only attempt reconnect on closed connection. Fixes [Issue #70](https://github.com/apollographql/subscriptions-transport-ws/issues/70)

## v0.5.0

- Updated `graphql-subscriptions@0.3.0`.
- Added `addGraphQLSubscriptions` - use it to extend your network interface to work with `SubscriptionsClient` instance. [PR #64](https://github.com/apollographql/subscriptions-transport-ws/pull/64)
- Client now uses native WebSocket by default, and has optional field to provide another implementation (for NodeJS clients)[PR #53](https://github.com/apollographql/subscriptions-transport-ws/pull/53)
- Client now support INIT with custom object, so you can use if for authorization, or any other init params. [PR #53](https://github.com/apollographql/subscriptions-transport-ws/pull/53)
- Server and client are now separated with `browser` and `main` fields of `package.json`. [PR #53](https://github.com/apollographql/subscriptions-transport-ws/pull/53)
- Client exposes workflow events for connect, disconnect and reconnect. [PR #53](https://github.com/apollographql/subscriptions-transport-ws/pull/53)
- Server exposes new events: `onUnsubscribe`, `onSubscribe`, `onConnect` and `onDisconnect`. [PR #53](https://github.com/apollographql/subscriptions-transport-ws/pull/53)
- Use `ws` package on server side, and expose it's options from server constructor. [PR #53](https://github.com/apollographql/subscriptions-transport-ws/pull/53)

## v0.4.0

- Don't throw in the server on certain unsub messages.
[PR #54](https://github.com/apollostack/subscriptions-transport-ws/pull/54)
- Moved typings to `@types/graphql`.
[PR #60](https://github.com/apollostack/subscriptions-transport-ws/pull/60)

## v0.3.1

- Server now passes back subscriptionManager errors encountered during publish.
[PR #42](https://github.com/apollostack/subscriptions-transport-ws/pull/42)

## v0.3.0

- (SEMVER-MINOR) Bump graphql-subscriptions dependency to ^0.2.0 which changes the setupFunctions format
- Fix missing unsubscription from first (id = 0) subscription

## v0.2.6

- Add `reconnect` and `reconnectionAttempts` options to the constructor which will enable reconnection with exponential backoff.

## v0.2.5

- Pass WebSocketRequest to onSubscribe to support reading HTTP headers when creating a subscription

## v0.2.4

- Server reports back an error on an unparsable client message
- Server reports back an error on an unsupported client message type
- Fix intermittent failure in timeout test case
- Standardize server and client errors handling to always create an array of errors with a message property
