# CHANGELOG

## 3.35.1
>2019-10-08

* FIX: extra comma on node v8 engine (#790)

## 3.35.0
>2019-09-26

* FEAT(remaining-validity): adds remaining valitity method (#778)
  * `client.getSecuredApiKeyRemainingValidity('securedAPIKey')`: Gets remaining validity seconds of an secured API Key
* FEAT(unit-testing-relevance): adds unit testing relevance methods (#777)
  * `index.findObject(hit => hit.firstname == 'Jimmie')`: Find an object by the given condition
  * `index.getObjectPosition(results, 'a-unique-identifier')`: Retrieve the given object position in the given results set
* FEAT(adds-assign-user-ids): adds assignUserIDs method and tests (#783)
  * `client.assignUserIDs({ cluster: 'c1-test', userIDs: ['some-user-1', 'some-user-2'] })`: Assign a array of userIDs to a cluster

## 3.34.0
>2019-08-29

* FEAT(index-exists): adds exists method into index (#773)
  * `index.exist()`: returns whether an index exists or not

## 3.33.0
>2019-05-09

* FEAT(api-keys): add restore api key method (#754)
  * `client.restoreApiKey('APIKEY')`: restore a deleted API key
  * see also https://www.algolia.com/doc/api-reference/api-methods/restore-api-key
* FIX(ua): change the User-Agent to use the new specs lib (version) (#747)

## 3.32.1
>2019-03-14

* FIX(errors): grammar change in error message (#737)
* FIX(dependencies): bump debug requirement (#746)

## 3.32.0
>2018-12-17

* FEAT(personalization): add new methods for the strategy
  * `getPersonalizationStrategy(cb)`: retrieve the currently set strategy
  * `setPersonalizationStrategy(strategy, cb)`: set the personalization strategy
    * a `strategy` is an object containing `eventsScoring` and `facetsScoring`
  * see also https://www.algolia.com/doc/rest-api/personalization

## 3.31.0
>2018-12-04

* FEAT(places): add `.reverse({ aroundLatLng: '' })` to reverse geo-code
* CHORE: deprecated `similarSearch()`, instead use `.search({ similarQuery: '' })`

## 3.30.0
>2018-08-01

* FIX(multi-query): property pass the `strategy` argument
  * as in [docs](https://www.algolia.com/doc/rest-api/search#method-param-strategy)
  * was originally put into url parameters instead of request body

## 3.29.0
>2018-06-20

* FEAT(analytics): add API methods for AB testing
  * find more info about the new feature here: https://blog.algolia.com/ab-testing-search/
  * adds a new method on client:
      import algoliasearch from 'algoliasearch';
      const client = algoliasearch('appid', 'apikey');
      const analytics = client.initAnalytics();
      analytics.getABTests().then(console.log)
  * see documentation here: https://www.algolia.com/doc/api-client/ab-test/
* CHORE(parse): remove parse build, not needed.
  * You can just install and `require('algoliasearch');`

## 3.28.0
>2018-06-13

* FEAT(cache): cache the requests instead of responses (#694)

  If you pass `_useRequestCache: true` as an option to the client then the cache behaviour will change. If you launch two requests at the same time then only one request will be done while the two callbacks/promises will still be called/resolved.

  Previously, the client would have made two requests instead of one.

  This is implemented by filling the cache as soon as the request launches instead of waiting for the response to fill it.
* FIX(parse): correct path to debug module (#702)

  fixes parse build, weirdly webpack is not throwing when importing an
  unknown module using target node
* TESTS: Make this CI green, fix unit and integration tests on every platform

## 3.27.1
>2018-05-03

* FIX: `client.searchForFacetValues` in older browsers
  * we use the polyfill implementation of Promise.all now instead of the native in 3.27.0
* FIX: `index.saveRule` throw when no objectID is given
* FEAT: deprecate index API key methods in favor of client ones
  * these methods will be removed, since you can add index restrictions to client API keys

## 3.27.0
>2018-04-16

* FEAT: add client.searchForFacetValues
  * this allows to request multiple search for facet values in a single call
  * note that this will do multiple requests (one per query)

## 3.26.0
>2018-03-21

* FEAT: allow disabling of dsn
  * in some cases (backend search while you do have global DSN), you want to disable DSN to avoid a round-robin around the whole world if DNS can't be resolved as expected, for example on GCP. (#675)

## 3.25.1
>2018-03-08

* FIX: fix protocol detection introduced in 3.25.0

## 3.25.0
>2018-03-07

* FEAT: use https by default (#670)
  * for very old devices https can be slow
  * we defaulted to sending API requests over http on http sites
  * this is now not really a performance bottleneck anymore
  * https is now default, unless specified differently when initializing

## 3.24.12
>2018-02-28

* FIX: Handle Node.js network errors more precisely (#669)

## 3.24.11
>2017-02-08

* FIX: allow `index.getSettings` without any arguments
  * this was a regression in 3.24.10
  * added tests

## 3.24.10
>2017-02-07

* FIX: correct `index.exportSynonyms` and `index.exportRules`
  * they had the wrong implementation until now
  * add some tests to prevent regression

## 3.24.9
>2017-12-29

* FIX: make sure long API keys are sent via the POST body
  * this wasn't the case in 3.24.8 because of a typo

## 3.24.8
>2017-12-13

* add multi cluster management methods
  * [ Assign or Move a userID to a cluster](https://algolia.com/doc/api-reference/api-methods/assign-user-id/): `assignUserID`
  * [Get userID with highest number of records per cluster](https://algolia.com/doc/api-reference/api-methods/get-top-user-id/): `getTopUserID`
  * [Returns the userID data stored in the mapping](https://algolia.com/doc/api-reference/api-methods/get-user-id/): `getUserID`
  * [List the clusters available in a multi-clusters setup for a single appID](https://algolia.com/doc/api-reference/api-methods/list-clusters/): `listClusters`
  * [List the userIDs assigned to a multi-clusters appID](https://algolia.com/doc/api-reference/api-methods/list-user-id/): `listUserIDs`
  * [Remove a userID and associated data from the multi-clusters](https://algolia.com/doc/api-reference/api-methods/remove-user-id/): `removeUserID`
  * [Search for userIDs](https://algolia.com/doc/api-reference/api-methods/search-user-id/): `searchUserIDs`

## 3.24.7
>2017-11-29

* don't throw an error when `copyIndex` without scope is used
  * if no scope is given, `settings`, as the default will be chosen

## 3.24.6
>2017-11-16

* add `index.exportSynonyms` and `index.exportRules`
  * they will get all of the synonyms or query rules on an index
* add a new `scope` argument to `copyIndex`
  * this is the third argument (from, to, scope)
  * it's an array with settings, synonyms or rules
  * if specified, that data will also be copied if you copy the index

## 3.24.5
>2017-10-02

* feat(deleteBy): add deleteBy
  * deleteByQuery is deprecated now
  * the same, but now it happens at the indexing side
  * no major changes should be seen, please report if any
  * https://github.com/algolia/algoliasearch-client-javascript/wiki/Deprecated#indexdeletebyquery

## 3.24.4
>2017-09-22

* chore(build): provide jsDelivr the right file (#599)

## 3.24.3
>2017-07-24

* chore(deprecation): remove deprecation from singular/plural methods; all these methods will stay existing
  * index.addObject(obj) or index.addObjects([obj])
  * index.partialUpdateObject(obj) or partialUpdateObjects([obj])
  * index.saveObject(obj) or index.saveObjects([obj])
  * index.deleteObject(objectID) or index.deleteObjects([objectID])
  * index.getObject(objectID) or index.getObjects([objectID])

## 3.24.2
>2017-07-24

* chore(deprecation): add deprecation message to all methods that will be removed in v4 (#573)
  * index.addObject(obj) --> index.addObjects([obj])
  * index.ttAdapter --> autocomplete.js
  * index.partialUpdateObject(obj) --> partialUpdateObjects([obj])
  * index.saveObject(obj) --> index.saveObjects([obj])
  * index.deleteObject(objectID) --> index.deleteObjects([objectID])
  * index.getObject(objectID) --> index.getObjects([objectID])
  * see https://github.com/algolia/algoliasearch-client-javascript/wiki/Deprecated for more information

## 3.24.1
>2017-07-20

* feat(headers): add functions to remove and get extra headers (#572)
  * client.setExtraHeader('X-cool-header','hello there');
  * client.getExtraHeader('X-cool-header'); //hello there
  * client.unsetExtraHeader('X-cool-header');
  * client.getExtraHeader('X-cool-header'); //undefined
* feat(deprecation): use console.warn to be more visible
* refact(rules): Adapt to latest JSON schema for Query Rules

## 3.24.0
>2017-06-21

* feat(rules): Add query rules beta version, you cannot use this for now

## 3.23.0
>2017-06-08

* feat(places): Add places.getObject(); fixes algolia/places#381

## 3.22.3
>2017-05-29

* fix(dependency): Do not pin debug dependency anymore
fixes #556

## 3.22.2
>2017-05-18

* fix(partialUpdateObjects): allow createIfNotExists (#552)
  Much like partialUpdateObject, allow createIfNotExists
  fixes #551

## 3.22.1
>2017-03-13

* fix(packaging): put back envify in deps
  * browserify transforms are applied for node_modules/pkg

## 3.22.0
>2017-03-13


* feat(API): rename all *userKey[s] methods to *apiKey[s]
  * client/index.listUserKeys() => client/index.listApiKeys()
  * client/index.getUserKeyACL() => client/index.getApiKey()
  * client/index.deleteUserKey() => client/index.deleteApiKey()
  * client/index.addUserKey() => client/index.addApiKey()
  * client/index.udpateUserKey() => client/index.updateApiKey()
* fix(packaging): remove useless files for packaging (reduce package file size)

## 3.21.1
>2017-02-08


* fix(browse*): use POST instead of GET to avoid limits (#503)

## 3.21.0
>2017-02-06


* feat(x-algolia-agent): specify x-algolia-agent at search time
* fix(parse): check for `global` existence before erasing

## 3.20.4
>2017-01-16


* fix(retry strategy): handle cases were localStorage fails after success (#474)

  Before this commit we only checked for localStorage failures at:
  - page load
  - localStorage.setItem

  While in some situations websites could erase localStorage for the
  whole page at any moment (between requests) and we were not resilient to that.

* chore(forwardToSlave): deprecate forwardToSlaves in favour or forwardToReplicas

## 3.20.3
>2017-01-04


* fix(agent): ensure algolia agent is not duplicated by successive calls

## 3.20.2
>2016-12-19


* fix(nodejs): do not use let, 0.12 does not support it

## 3.20.1
>2016-12-17


* fix(nodejs): on timeout, destroy the right response

## 3.20.0
>2016-12-14


* feat(retry strategy): adjust retry strategy for all implementations
  - Retry strategy now shares the last known host for a specific appId across the current domain (browsers)
  or the current process (browsers without localStorage, Node.js). After 2 minutes we try to target back
  the first host (Usually DSN)
  - Retry strategy now shares the last known timeout multiplier that worked and set it back to default
  after 2 minutes
  - Retry strategy on Node.js now has a connect timeout of 2s
  - Retry strategy on browsers (JavaScript, not jQuery, not Angular.js, not React Native for now) now
  has a connect timeout of 1s
  - You can now get and set timeouts per client with .setTimeouts({connect, read, write}), .getTimeouts().
  Values are in ms.

## 3.19.2
>2016-11-28


* fix(facet search): rename index.searchFacet to index.searchForFacetValues

## 3.19.1
>2016-11-11


* fix(build): use regular debug module, issue with yui compressor was fixed here:
https://github.com/visionmedia/debug/pull/315

## 3.19.0
>2016-10-26


* feat(index.searchFacet): add method #345

## 3.18.1
>2016-08-31


* fix(client.search): accept very long API keys
  fixes #319

  also fix uglify-js version because it's buggy in IE8:
  https://github.com/mishoo/UglifyJS2/issues/1039

## 3.18.0
>2016-07-22


* fix(debug): only activate debug messages on NODE_ENV==='debug'
* feat(lite): add getObjects

## 3.17.0
>2016-07-06


* feat(errors): add statusCode to errors
* chore(shrinkwrap): completely remove shrinkwrap

## 3.16.0
>2016-06-22


* feat(index.setSettings): add forwardToSlaves option
index.setSettings({settings}, {forwardToSlaves}, cb);
see https://www.algolia.com/doc/rest#change-index-settings

## 3.15.1
>2016-06-16


* fix(getLogs): allow using the type parameter
  The syntax is now getLogs(params[, cb])
  fixes #232
* fix(json): avoid throwing when late JSON response
  fixes #284
* fix(nodejs): allow universal lite applications
  require('algoliasearch/lite') should work to
  facilitate universal applications builds using
  the lite build on frontend

fixes #283

## 3.15.0
>2016-06-07


* feat(synonyms): add new synonyms API

## 3.14.6
>2016-05-30


* fix(places): allow empty credentials

## 3.14.5
>2016-05-26


* fix(window): don't assume window is here

When required in a node context, we may load the browser build without
using it. Just for testing other parts of it.

## 3.14.4
>2016-05-25


* fix(lite): lite package should have browse and browseFrom

## 3.14.3
>2016-05-25


* fix(retry): also retry on non search methods when DNS failure

  Before this commit, methods with no fallback support (basically every
  method) would fail at retry if the DNS error occurred before the API
  client timeout.

  The behavior is now:
  - when a method with a fallback errors because of DNS failure we will
  switch to JSONP right away
  - when a method with no fallback errors because of DNS failure we will
  still retry

  We could use the same mechanism for both (= always try all hosts
  before JSONP) but I am not confident doing this change within a patch
  or minor version. We have too litle data on how blocked XHRS are
  triggered (async, sync?).

  fixes #250

  * fix(request strategy): comply with retry spec, no early JSONP switch

    This commit brings more conformance with request strategy
    specification by only raising timeout when there's a timeout.

    It also stop trying to switch to JSONP asap and always try all hosts
    using XHRS before.

## 3.14.2
>2016-05-24


* fix(request strategy): increments hostIndex (host address) on fallback

  When we are switching to fallback, increment host index so that JSONP
  will use another host.

  This issue was caused because we cannot distinguish CORS errors from DNS
  resolution errors in the browser.

  And the code for incrementing the host index was moved into the part
  that switches to the fallback in
  4ec5e6a1f8cd92924ce025d60646b3a47b7d8dca.

  Truth is that the current solution is not optimal as, in the browser,
  we are switching to JSONP when we can't resolve the server name.

  This is only done because we are not sure how CORS request can be
  blocked (synchronously, asynchronously).

  In a next version we would drop it and wait for real issues to show up.

## 3.14.1
>2016-05-12


* fix(retry strategy): retry on timeout was only using two hosts
* fix(errors): provide err.debugData with necessary debugging information
* fix(errors): force AlgoliaSearchError as default name
fixes #241

## 3.14.0
>2016-05-04


* feat(client.search): add strategy, fixes #208
* fix(shuffle): shuffle host array like we did
* feat(filesize): reduce filesize by removing lodash
  All build size down 26% (20kb => 14kb)
  New search-only build "algoliasearchLite[.min].js",
  weights 9.5Kb (down 50% from normal build)
  Also available as require('algoliasearch/lite');
* fix(parse): handle parse cloud env having process.env defined

## 3.13.1
>2016-03-24


* chore(dev): use phantomjs-prebuilt instead of phantomjs
fixes #209

## 3.13.0
>2016-02-23


* feat(initPlaces): add a static algoliasearch.initPlaces method

## 3.12.0
>2016-02-05


* fix(apiKey): put the apiKey in the POST body when feasible and key > 500 chars
* feat(falback): provide opts.useFallback to avoid using JSONP fallback

## 3.11.0
>2016-01-28


* feat(partialUpdateObject): add createIfNotExists option: partialUpdateObject(object, createIfNotExists) https://www.algolia.com/doc/rest#partially-update-an-object
* chore(dev): various fixes to the dev env

## 3.10.2
>2015-12-14


* fix(request strategy): always use XHR first then switch to fallback

  + add fallback for client.search

  Context: before this commit, when a user lost connectivity (or XHR was
  blocked, we cannot distinguish those events in browsers) then we
  forced using JSONP for the whole session.

  This led to a bug where you were stuck in a loop of non-available
  fallback even if connectivity was restored.

  This commit fixes this bug by always trying XHRS and fallbacking to
  JSONP on a per request basis.
* refactor(map): use lodash map instead of custom fn

## 3.10.1
>2015-12-11

* fix(nodejs): consistent timeouts between nodejs versions
  We now use basic setTimeout functionnality instead of
  req.setTimeout in nodejs to avoid inconsistencies between nodejs engines.
  In node 0.10, req.setTimeout was a socket inactivity timeout
  In node > 0.10? req.setTimeout is now a global timeout
  + Node.js timeout is now 30s global per request (then incremental)
  + Fixed an edge case where we had an uncaught exception in nodejs
  + We only support 0.10+ now, node 0.8 never worked

## 3.10.0
>2015-12-08

* feat(gzip): ask the API for gzipped answers (nodejs)

## 3.9.4
>2015-12-04

* fix(process.env): set process back to normal in node v4

## 3.9.3
>2015-12-01

* fix(parse): set default timeout to 7.5s (indexing purposes)

## 3.9.2
>2015-11-02

* feat: react native build beta

## 3.9.1
>2015-11-02

* fix: throw on really bad usage instead of silently failing
* fix: make angular build cache work

## 3.9.0
>2015-10-23

* feat: add similarSearch beta method
* feat: add new way to generate secured api key using query parameters

## 3.8.1
>2015-09-21


* fix: disable chunked encoding on empty body DELETE requests in Node.js

## 3.8.0
>2015-09-01


* test: node v4 is now the default testing env
* fix: always send a unique response to the user
* fix: use `lodash` by default, only use `lodash-compat` when building for the browser
* feat: add client.addAlgoliaAgent() to augment the sent x-algolia-agent
* chore: move all deps to ^version and add a shrinkwrap to allow reproducible builds

## 3.7.8
>2015-09-01


* fix: ignore $http.defaults.headers.common in angular build
* fix: force distinct false in deleteByQuery search
* docs: precise initialization option values

## 3.7.7
>2015-08-27

* fix: listen to socket errors in nodejs keepalive strategy

## 3.7.6
>2015-08-24

* fix: encodeURIComponent(cursor) in browseFrom()

## 3.7.5
>2015-07-23

* fix: withCredentials forced to false in Angular

## 3.7.4
>2015-07-20

* fix: JSON.stringify fix when Array.prototype.toJSON is defined (prototype.js < 1.7 bug)

## 3.7.3
>2015-07-09

* fix: make https over http proxy work

## 3.7.2
>2015-07-08

* fix: remove a git clone dependency on install (debug/ms/yui compressor issue)

## 3.7.1
>2015-07-08

* fix: do not call agent.destroy when there's no such method
* fix: do not rely on any "smart" port computing

## 3.7.0
>2015-06-18

* feat: allow passing `httpAgent` option to the nodejs client
allow more flexible proxy/keepAlive agents in some more complex environments

## 3.6.3
>2015-06-18

* fix: allow getting the debug log from the outside
  will be used by diag tool and possibly anyone aware of https://github.com/visionmedia/debug

## 3.6.2
>2015-06-17

* chore: add window.__algolia for easy debugging anywhere

## 3.6.1
>2015-06-16

* fix: parse cloud build fix
* fix: YUI compressor fix
  fixes #113
* test: automatic parse cloud build testing
* fix: add application id to final error message ("Cannot connect to..")

## 3.6.0
>2015-06-05

* feat: easy commonJS require of plugins
  fixes #109
* test: add dependency-check step in tests
* refactor: use lodash-compat instead of less known/used/shared modules
* chore: use uglifyjs instead of closure compiler
* feat: allow passing hosts as hosts.read, hosts.write
* feat: allow passing Algolia Agent as an option
* fix: CORS simple request for all browser builds
  fixes #111

## 3.5.0
>2015-06-03

* fix: send a descriptive timeout error when it occurs
* chore: add headers debugging
* fix: incremental wait waitTask
  will now wait 100ms * loopTickNumber * loopTickNumber
  fixes #102
* fix: do not use global when we know we will be in a browser
  browserify `global` is not always `window` can be <div id="global"></div>
  fixes #99
* feat: new browse()/browseFrom()/browseAll()
  - `browse(query, queryParameters)` now has the same signature than
  search(). You can use any `query` and `queryParameters`.
  - `browseFrom(cursor)` can be used as an efficient way to
  continue (next page) a previous `browse()` call. All browse responses now have a `cursor` property.
  - `browseAll(query, queryParameters)` can be used to get all
  the content of your index
    It returns an [EventEmitter](https://nodejs.org/api/events.html).

    Available events:
      - `result`
      - `end`
      - `error` (you should listen to it or it will throw)

    There's also `stop()` method on the event emitter so that you can
    stop browsing at any point.

  fixes #101
* fix: support typeahead 0.11
  fixes #105

## 3.4.0
>2015-05-23

* FIX: Remove debugging messages from builds
  fixes #91
  fixes #86
* FIX: Handle badly formatted JSON
  fixes #89
  fixes #90
* FIX: Stop bytes sent/received debug on node 0.12 when socket closes
* test: Test on only 3 browsers in travis
  fixes #61
* test: split desktop/mobile into a travis matrix, reduces travis timeouts
* feat: add client.batch()
* feature: getObjects now accepts attributesToRetrieve:
  signature: getObjects(objectIDs, attributesToRetrieve, callback)
* fix: send `x-algolia-agent` instead of `x-user-agent`
* fix: clone cached results hits sent
  fixes #79
* feat: New parameters for API keys
  Added description, referers, queryParameters
  ref: https://www.algolia.com/changes#released-##
  >2015-05-08

* fix: IE11 xhr cache was fixed by adding cache-control: no-cache in API headers
* test: add integration testing and rework the travis tasks

##  3.3.2
>2015-05-14

* FIX: more fixes to the use of $q() in the angular build, now compatible with 1.2.xx and tested

##  3.3.1
>2015-05-12

* FIX: Compatibility with AngularJS old promise implementation
  We now use $q.defer() instead of $q()

##  3.3.0
>2015-05-12

* FEATURE: expose window.algoliasearch = algoliasearch in jquery/angular plugins. So that
you can use the original algoliasearch() implem in plugins. Otherwise you would have to load both

##  3.2.4
>2015-05-11

* FIX: 15s inactivity timeout for nodejs implementation, should help high latency/low connection users
* CHORE: test on iojs2
* CHORE: debugging messages now more focused and less verbose
* PERF: use JSON.stringify only once per request

##  3.2.3
>2015-05-09

* FIX: Parse build requires a charset on requests

##  3.2.2
>2015-05-06

* FIX :  missing require (crypto) for node.js client (#84)

##  3.2.1
>2015-04-29

* add dist/ to npmjs repository, so cdnjs autoupdate works

##  3.2.0
>2015-04-24

* FEATURE: Parse build now uses V3 implementation
* FEATURE: Parse build now returns parse promises. https://parse.com/docs/js_guide#promises
* FEATURE: Automatically handle HTTP_PROXY HTTPS_PROXY environment variables
in Node.js client

##  3.1.0
>2015-04-14

* CHANGE: Node.js will now use http headers instead of inlining them into the api call as browsers are doing
* CHANGE: Ensure all headers (http, querystrings) are lowercased. Both are supported by our API, reduces FUD
* FEATURE: add index.getObjects()
* FEATURE: add index.deleteObjects()
* FIX: waitTask failure case when using promises, was not going through
* FEATURE: add index.deleteByQuery()
* FEATURE (Node.js): add client.enableRateLimitForward()
* FEATURE (Node.js): add client.disableRateLimitForward()
* FEATURE (Node.js): add client.useSecuredAPIKey()
* FEATURE (Node.js): add client.disableSecuredAPIKey()
* BREAKING CHANGE (Node.js): client.setTimeout renamed to client.setRequestTimeout
* TEST: add test around setRequestTimeout
* FEATURE (Node.js): add client.generateSecuredApiKey()
* FEATURE:
  - all clients are now exposing algoliasearch.ua
  - all requests are now sending x-user-agent containing for example 'Algoliasearch for vanilla JavaScript 3.0.7'
* FEATURE: add client.search()
  Search against multiple indices, equivalent of, multipleQueries, or
  startQueriesBatch+addQueryInBatch+sendQueriesBatch
* BREAKING CHANGE (Node.js): removed client.multipleQueries(), use client.search(queries)
* DEPRECIATION (browser): client.startQueriesBatch/addQueryInBatch/sendQueriesBatch
  Use client.search(queries)
* FEATURE: new HA implementation
  We now use two different DNS to perform all requests
  Removed the tld option as it's no more needed nor compatible with having a new HA implementation with different tlds (.com/.net)
* DEPRECIATION: client.addUserKeyWithValidity(), index.addUserKeyWithValidity()
  You can now use client.addUserKey(acls, params, cb), index.addUserKey(acls, params, cb)
* FEATURE: client|index.updateUserKey(key, acls, params, callback)
  Update a user key, provide acls and optional params
* BREAKING CHANGE (Node.js):
  As we now have addUserKey and updateUserKey, we removed:
    - client|index.addUserKeyWithValidityAndIndexes
    - client|index.updateUserKeyWithValidity
    - client|index.updateUserKeyWithValidityAndIndexes
  You can use client|index.addUserKey or client|index.updateUserKey to do
  deal with all you keys needs

##  3.0.7
>2015-04-10

* MIGRATION: throw on V2 .search() usage:
  - .search(query, cb, params)
  - .search(cb, params)
* FEATURE: add client.destroy() in Node.js implementation
  will destroy all keepalived connections and let the process exits if needed

##  3.0.6
>2015-04-03

* FIX: Webpack compatibility by removing packageify
  webpack does not interprets for now node_modules/* browserify transforms
* MISC: add release script

##  3.0.5
>2015-04-02

* FIX: lower the build size by requiring the good version/browser.js in browser
  builds. Previously we got the full `package.json` inlined

##  3.0.4
>2015-04-02

* FIX: Defaults to http when the protocol of the page is not http or
  https
* FIX: XDomainRequests no more aborted in IE9 #76

##  3.0.3
>2015-03-28


* FIX: Handle module loaders + cdn.jsdelivr.net/algoliasearch/latest usage
  When in this situation, the module loader would prevent the code
  detecting and loading the V2 to execute.
  Now fixed by prepending the migration-layer to the browserify bundle.
  It also removes the migration-layer code from the package managers (npm, bower) builds,
  where it makes no sense to have it
* FIX: load V2 using a DOMElement when V3 is loaded ASYNCHRONOUSLY with /latest/
  * tested on all majors browsers:
    Chrome stable
    Firefox stable
    IE 8, 9, 10, 11
  * tested on corresponding customer websites
* FIX: better warning messages when using `latest` or trying to use V3 as V2

##  3.0.2
>2015-03-26


* temp /latest/ fix for some clients loading /latest/ in async mode

##  3.0.1
>2015-03-26


* fix npm usage, was missing a dependency

##  3.0.0
>2015-03-25


* V2 users, see the migration guide at https://github.com/algolia/algoliasearch-client-js/wiki/Migration-guide-from-2.x.x-to-3.x.x
* BREAKING CHANGES:
  * `new AlgoliaSearch()` => `algoliasearch()` #40
    - The only exported global property is now `algoliasearch`
    - `opts`:
      - `dsnHost` removed, use `hosts:[dsnHost, other hosts]`
      - `dsn` removed, use `hosts:[non-dsn-host, non-dsn-host]`
      - `requestTimeoutInMs` renamed to `timeout`
      - `method` renamed to `protocol`. Protocol should be specified as `http:` or `https:`
      - `hosts` behavior changed, when using custom hosts:
        - no shuffling
        - no dsn host is prepended to the list
    - removed `AlgoliaExplainResults`, no obvious use ATM
    - calling algoliasearch() without an applicationID or apiKey will throw
    - Helper: `new AlgoliaSearchHelper()` => `algoliasearch.helper()`, same function signature
  * no more window.ALGOLIA_VERSION
    - you can find the version in algoliasearch.version
  * all api methods now use the (err, content) convention #43
    It means that instead of doing:
      ```js
        index.search(function found(success, content) {
          if (!success) {
            console.log('Error was:', content);
            return;
          }

          console.log('OK!', content);
        });
      ```
    You must do:
      ```js
        index.search(function found(err, content) {
          if (err) {
            console.log('Error was:', err);
            return;
          }

          console.log('OK!', content);
        });
      ```
    This is in par with most asynchronous APIS accepted/de vfacto conventions.
    It helps being compatible with control flow libraries like `async` and
    helps reduce WTF moments of Node.JS developers used to cb(err, content)
  * client.getLogs(cb[, offset, length]) is now .getLogs([offset, length, cb])
  * client.listIndexes(cb[, page]) => .listIndexes([page, cb])
  * client|index.addUserKeyWithValidity(acls, validity, maxQueriesPerIPPerHour, maxHitsPerQuery, cb) => client|index.addUserKeyWithValidity(acls, params, cb) where params = {validity:, maxQueriesPerIPPerHour:, maxHitsPerQuery:}
  * client.sendQueriesBatch(cb, delay) => client.sendQueriesBatch(cb)
  * index.addObject(content[, callback, objectID]) => index.addObject(content[, objectID, callback])
  * index.getObject(objectID[, callback, attributes]) => index.getObject(objectID[, attrs, callback])
  * index.search(query, callback[, params, delay]) => index.search(query[, params callback]) or index.search(params[, cb]) with params = {query: 'some thing'}
    We removed the delay option which should really be implemented by the module consumer. It's really a throttle/debounce of the search functions
  * index.browse(page, cb[, hitsPerPage]) => index.browse(page[, hitsPerPage, cb])
  * no more opts.jsonp in algoliasearch()
    Previously used as a way to force/disable jsonp. The request strategy is now more robust and does not
    requires jsonp: param
    * JSON2.js is no more included in the main build.
      If you need to support IE7 <= or IE8 quirks, add this:
        ```html
        <!--[if lte IE 7]>
        <script src="//cdn.jsdelivr.net/json2/0.2/json2.min.js"></script>
        <![endif]-->
        ```
    * removed AlgoliaSearchHelper
      Please see https://github.com/algolia/algoliasearch-helper-js if you need the helper
  * NEW FEATURES:
    * UMD compatibility #41
      - algoliasearch can now be used with any module loader
      - build is now done with browserify
      - no more grunt
  * All calls are now returning promises #45
    If there's a callback given to an API call, you won't get a promise.
    Here are the different promises implementations we use:
    - Native promises by default (https://github.com/jakearchibald/es6-promise/)
    - AngularJS promises for AngularJS plugin
    - jQuery promises for jQuery plugin
* FIXES:
  * do not retry when server sends 4xx or 1xx
  * distinguish jQuery/AngularJS request timeouts from errors and thus retry when timeout
  * JSONP fallback when jQuery/AngularJS request error
* MISC:
  * Externalize plugins and request implementations
  * some linting fixes
  * test suite, including request strategy test suite
  * IE10 should now behave as a CORS supported XMLHttpRequest browser, as it is
  * running tests on many browsers, using saucelabs
  * removed vendor/
    - vendor/json2.js
    - vendor/jquery.typeahead.js now on cdnjs (examples)

##  2.9.2
>2015-02-03

* Fixed calls to `.search(function() {})`, `.search(null, function() {})`, `.search(undefined, function() {})
* Fixed shared cache amongst instances

##  2.9.1
>2015-02-03

* Fixed listIndexes pagination, not working if page=0

##  2.9.0
>2015-01-13

* Angular.js & jQuery compatibility (returning promises)
* Helper: ability to exclude facets

##  2.8.6
>2015-01-13

* Search helper: ability to set default facet filters

##  2.8.5
>2015-01-07

* Avoid CORS preflight request

##  2.8.4
>2014-12-31

* Fixed a bug in JSONP fallback on multi-queries and getObject when a secured API Key was used (X-Algolia-TagFilters parameter was not set, resulting in a 403 permission denied error)

##  2.8.3
>2014-12-30

* Helper optimization: number of nested queries is now driven by the number of refined disjunctive facets only

##  2.8.2
>2014-12-23

* Increase the request timeout after each retry

##  2.8.1
>2014-12-09

* Enabled DSN by default (is working even if only one datacenter is selected)

##  2.8.0
>2014-11-28

* Move to algolia.net by default

##  2.7.5
>2014-11-25

* Expose one option to select the TTL (prepare migration to .net, allow to gain some milliseconds compared to .io)

##  2.7.4
>2014-11-12

* Expose more options (jsonp & requestTimeoutInMs)
* Change the way the JSONP fallback works

##  2.7.3
>2014-10-29

* Reintroduced Algolia Custom Headers (X-Algolia-*) on queries. It was removed to try to remove the CORS OPTIONS query but this has no impact because this is a POST action.

##  2.7.2
>2014-10-27

* Fixed browse method (author @muertet)

##  2.7.{0,1}
>2014-10-15

* Refactor the AlgoliaSearch constructor to allows optional/named arguments

##  2.6.6
>2014-10-07

* Fixed bower integration

##  2.6.5
>2014-09-26

* Optimize disjunctive queries that were retrieving useless attributes

##  2.6.4
>2014-09-23

  * Fixed CORS handling issue on IE8/IE9

##  2.6.3
>2014-09-23

  * Fixed IE11-based AJAX calls

##  2.6.2
>2014-09-20

  * Updated package manager description files: npm and jsdelivr

##  2.6.1
>2014-09-20

  * Fixed JSONP call: 'X-Algolia-TagFilters' and 'X-Algolia-UserToken' were not included in the URL.

##  2.6.0
>2014-09-06

  * Improved retry strategy with implementation of a timeout on network call.
    Upgrade to this version is highly recommended

##  2.5.4
>2014-09-04

* Removed the OPTIONS request for the first isalive query of for all search queries

##  2.5.3
>2014-07-23

* AlgoliaSearchHelper: add missing getIndex/setIndex
* listIndexes is now paginable

##  2.5.2
>2014-06-05

* AlgoliaSearchHelper: add getter/setter methods

##  2.5.1
>2014-05-14

* Fixed listIndexes call (trailing slash not compatible with our API anymore)

##  2.5.0
>2014-05-09

* If CORS is not available, use JSONP

##  2.4.7
>2014-04-23

* Ability to instantiate multiple AlgoliaSearchHelper

##  2.4.6
>2014-04-05

* Fixed IE 8/9 support of secured API keys

##  2.4.5
>2014-03-30

* Improved AlgoliaExplainResults helper handling array-based attributes as well.

##  2.4.4
>2014-03-19

* Improved the `waitTask` method, ensuring it sleeps 100ms before recalling the API.

##  2.4.3
>2014-03-12

* Removed invalid character from source code (could cause a parse error in IE8/9)

##  2.4.2
>2014-02-24

* Added support of secured API Key (SecurityTags & UserToken headers)

##  2.4.1
>2014-02-18

* Removed dependency on jquery

##  2.4.0
>2014-02-10


* Move to official Typeahead.js release (0.10.1)
* Remove getTypeAheadTransport* functions

##  2.3.8
>2014-01-16


* Ability to customize getTypeAheadTransport parameters once instantiated

##  2.3.7
>2014-01-08


* Remove extra encodeURI
* Travis integration

##  2.3.6
>2014-01-06


* Missing encodeURI
* Added "distinct" documentation

##  2.3.5
>2013-12-06


* Added browse methods

## 2.3.4-1
>2013-12-04


* Fixed IE9 bug while reading onload's event
* Here and there typos

## 2.3.0
>2013-11-07


* Added new ACL features (maxQueriesPerIPPerHour & maxHitsPerQuery)

## 2.2.0
>2013-11-07


* Added clearIndex method

## 2.1.0
>2013-11-03


* Auto-detect protocol to used based on current location
* Added auto-complete & instant-search examples

## 2.0.1
>2013-10-15


* Gruntification
* Embed typeahead.js
