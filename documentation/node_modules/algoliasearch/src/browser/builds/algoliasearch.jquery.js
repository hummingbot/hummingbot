'use strict';

// This is the jQuery Algolia Search module
// It's using $.ajax to do requests with a JSONP fallback
// jQuery promises are returned

var inherits = require('inherits');

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

function algoliasearch(applicationID, apiKey, opts) {
  var cloneDeep = require('../../clone.js');

  opts = cloneDeep(opts || {});

  opts._ua = opts._ua || algoliasearch.ua;

  return new AlgoliaSearchJQuery(applicationID, apiKey, opts);
}

algoliasearch.version = require('../../version.js');

algoliasearch.ua =
  'Algolia for JavaScript (' + algoliasearch.version + '); ' +
  'jQuery (' + window.jQuery().jquery + ')';

algoliasearch.initPlaces = places(algoliasearch);

// we expose into window no matter how we are used, this will allow
// us to easily debug any website running algolia
window.__algolia = {
  debug: require('debug'),
  algoliasearch: algoliasearch
};

var $ = window.jQuery;

$.algolia = {
  Client: algoliasearch,
  ua: algoliasearch.ua,
  version: algoliasearch.version
};

function AlgoliaSearchJQuery() {
  // call AlgoliaSearch constructor
  AlgoliaSearch.apply(this, arguments);
}

inherits(AlgoliaSearchJQuery, AlgoliaSearch);

AlgoliaSearchJQuery.prototype._request = function request(url, opts) {
  return new $.Deferred(function(deferred) {
    var body = opts.body;

    url = inlineHeaders(url, opts.headers);

    var requestHeaders = {
      accept: 'application/json'
    };

    if (body) {
      if (opts.method === 'POST') {
        // https://developer.mozilla.org/en-US/docs/Web/HTTP/Access_control_CORS#Simple_requests
        requestHeaders['content-type'] = 'application/x-www-form-urlencoded';
      } else {
        requestHeaders['content-type'] = 'application/json';
      }
    }

    $.ajax(url, {
      type: opts.method,
      timeout: opts.timeouts.complete,
      dataType: 'json',
      data: body,
      headers: requestHeaders,
      complete: function onComplete(jqXHR, textStatus/* , error*/) {
        if (textStatus === 'timeout') {
          deferred.reject(new errors.RequestTimeout());
          return;
        }

        if (jqXHR.status === 0) {
          deferred.reject(
            new errors.Network({
              more: jqXHR
            })
          );
          return;
        }

        deferred.resolve({
          statusCode: jqXHR.status,
          body: jqXHR.responseJSON,
          responseText: jqXHR.responseText,
          headers: jqXHR.getAllResponseHeaders()
        });
      }
    });
  }).promise();
};

// using IE8 or IE9 we will always end up here
// jQuery does not not fallback to XDomainRequest
AlgoliaSearchJQuery.prototype._request.fallback = function requestFallback(url, opts) {
  url = inlineHeaders(url, opts.headers);

  return new $.Deferred(function wrapJsonpRequest(deferred) {
    jsonpRequest(url, opts, function jsonpRequestDone(err, content) {
      if (err) {
        deferred.reject(err);
        return;
      }

      deferred.resolve(content);
    });
  }).promise();
};

AlgoliaSearchJQuery.prototype._promise = {
  reject: function reject(val) {
    return new $.Deferred(function rejectDeferred(deferred) {
      deferred.reject(val);
    }).promise();
  },
  resolve: function resolve(val) {
    return new $.Deferred(function resolveDeferred(deferred) {
      deferred.resolve(val);
    }).promise();
  },
  delay: function delay(ms) {
    return new $.Deferred(function delayResolve(deferred) {
      setTimeout(function resolveDeferred() {
        deferred.resolve();
      }, ms);
    }).promise();
  },
  all: function all(promises) {
    return $.when.apply(null, promises);
  }
};
