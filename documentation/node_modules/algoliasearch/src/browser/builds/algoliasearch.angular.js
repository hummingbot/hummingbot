'use strict';

// This is the AngularJS Algolia Search module
// It's using $http to do requests with a JSONP fallback
// $q promises are returned

var inherits = require('inherits');

var forEach = require('foreach');

var AlgoliaSearch = require('../../AlgoliaSearch');
var errors = require('../../errors');
var inlineHeaders = require('../inline-headers');
var jsonpRequest = require('../jsonp-request');
var places = require('../../places.js');

// expose original algoliasearch fn in window
window.algoliasearch = require('./algoliasearch');

if (process.env.NODE_ENV === 'debug') {
  require('debug').enable('algoliasearch*');
}

window.angular.module('algoliasearch', [])
  .service('algolia', ['$http', '$q', '$timeout', function algoliaSearchService($http, $q, $timeout) {
    function algoliasearch(applicationID, apiKey, opts) {
      var cloneDeep = require('../../clone.js');

      opts = cloneDeep(opts || {});

      opts._ua = opts._ua || algoliasearch.ua;

      return new AlgoliaSearchAngular(applicationID, apiKey, opts);
    }

    algoliasearch.version = require('../../version.js');

    algoliasearch.ua =
      'Algolia for JavaScript (' + algoliasearch.version + '); ' +
      'AngularJS (' + window.angular.version.full + ')';

    algoliasearch.initPlaces = places(algoliasearch);

    // we expose into window no matter how we are used, this will allow
    // us to easily debug any website running algolia
    window.__algolia = {
      debug: require('debug'),
      algoliasearch: algoliasearch
    };

    function AlgoliaSearchAngular() {
      // call AlgoliaSearch constructor
      AlgoliaSearch.apply(this, arguments);
    }

    inherits(AlgoliaSearchAngular, AlgoliaSearch);

    AlgoliaSearchAngular.prototype._request = function request(url, opts) {
      // Support most Angular.js versions by using $q.defer() instead
      // of the new $q() constructor everywhere we need a promise
      var deferred = $q.defer();
      var resolve = deferred.resolve;
      var reject = deferred.reject;

      var timedOut;
      var body = opts.body;

      url = inlineHeaders(url, opts.headers);

      var timeoutDeferred = $q.defer();
      var timeoutPromise = timeoutDeferred.promise;

      $timeout(function timedout() {
        timedOut = true;
        // will cancel the xhr
        timeoutDeferred.resolve('test');
        reject(new errors.RequestTimeout());
      }, opts.timeouts.complete);

      var requestHeaders = {};

      // "remove" (set to undefined) possible globally set headers
      // in $httpProvider.defaults.headers.common
      // otherwise we might fail sometimes
      // ref: https://github.com/algolia/algoliasearch-client-js/issues/135
      forEach(
        $http.defaults.headers.common,
        function removeIt(headerValue, headerName) {
          requestHeaders[headerName] = undefined;
        }
      );

      requestHeaders.accept = 'application/json';

      if (body) {
        if (opts.method === 'POST') {
          // https://developer.mozilla.org/en-US/docs/Web/HTTP/Access_control_CORS#Simple_requests
          requestHeaders['content-type'] = 'application/x-www-form-urlencoded';
        } else {
          requestHeaders['content-type'] = 'application/json';
        }
      }

      $http({
        url: url,
        method: opts.method,
        data: body,
        cache: false,
        timeout: timeoutPromise,
        headers: requestHeaders,
        transformResponse: transformResponse,
        // if client uses $httpProvider.defaults.withCredentials = true,
        // we revert it to false to avoid CORS failure
        withCredentials: false
      }).then(success, error);

      function success(response) {
        resolve({
          statusCode: response.status,
          headers: response.headers,
          body: JSON.parse(response.data),
          responseText: response.data
        });
      }

      // we force getting the raw data because we need it so
      // for cache keys
      function transformResponse(data) {
        return data;
      }

      function error(response) {
        if (timedOut) {
          return;
        }

        // network error
        if (response.status === 0) {
          reject(
            new errors.Network({
              more: response
            })
          );
          return;
        }

        resolve({
          body: JSON.parse(response.data),
          statusCode: response.status
        });
      }

      return deferred.promise;
    };

    // using IE8 or IE9 we will always end up here
    // AngularJS does not fallback to XDomainRequest
    AlgoliaSearchAngular.prototype._request.fallback = function requestFallback(url, opts) {
      url = inlineHeaders(url, opts.headers);

      var deferred = $q.defer();
      var resolve = deferred.resolve;
      var reject = deferred.reject;

      jsonpRequest(url, opts, function jsonpRequestDone(err, content) {
        if (err) {
          reject(err);
          return;
        }

        resolve(content);
      });

      return deferred.promise;
    };

    AlgoliaSearchAngular.prototype._promise = {
      reject: function(val) {
        return $q.reject(val);
      },
      resolve: function(val) {
        // http://www.bennadel.com/blog/2735-q-when-is-the-missing-q-resolve-method-in-angularjs.htm
        return $q.when(val);
      },
      delay: function(ms) {
        var deferred = $q.defer();
        var resolve = deferred.resolve;

        $timeout(resolve, ms);

        return deferred.promise;
      },
      all: function(promises) {
        return $q.all(promises);
      }
    };

    return {
      Client: function(applicationID, apiKey, options) {
        return algoliasearch(applicationID, apiKey, options);
      },
      ua: algoliasearch.ua,
      version: algoliasearch.version
    };
  }]);
