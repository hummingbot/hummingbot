'use strict';

// Some methods only accessible server side

module.exports = AlgoliaSearchServer;

var inherits = require('inherits');

var AlgoliaSearch = require('../../AlgoliaSearch');

function AlgoliaSearchServer(applicationID, apiKey, opts) {
  // Default protocol is https: on the server, to avoid leaking admin keys
  if (opts.protocol === undefined) {
    opts.protocol = 'https:';
  }

  AlgoliaSearch.apply(this, arguments);
}

inherits(AlgoliaSearchServer, AlgoliaSearch);

/*
 * Allow to use IP rate limit when you have a proxy between end-user and Algolia.
 * This option will set the X-Forwarded-For HTTP header with the client IP and the X-Forwarded-API-Key with the API Key having rate limits.
 * @param adminAPIKey the admin API Key you can find in your dashboard
 * @param endUserIP the end user IP (you can use both IPV4 or IPV6 syntax)
 * @param rateLimitAPIKey the API key on which you have a rate limit
 */
AlgoliaSearchServer.prototype.enableRateLimitForward = function(adminAPIKey, endUserIP, rateLimitAPIKey) {
  this._forward = {
    adminAPIKey: adminAPIKey,
    endUserIP: endUserIP,
    rateLimitAPIKey: rateLimitAPIKey
  };
};

/*
 * Disable IP rate limit enabled with enableRateLimitForward() function
 */
AlgoliaSearchServer.prototype.disableRateLimitForward = function() {
  this._forward = null;
};

/*
 * Specify the securedAPIKey to use with associated information
 */
AlgoliaSearchServer.prototype.useSecuredAPIKey = function(securedAPIKey, securityTags, userToken) {
  this._secure = {
    apiKey: securedAPIKey,
    securityTags: securityTags,
    userToken: userToken
  };
};

/*
 * If a secured API was used, disable it
 */
AlgoliaSearchServer.prototype.disableSecuredAPIKey = function() {
  this._secure = null;
};

AlgoliaSearchServer.prototype._computeRequestHeaders = function(additionalUA) {
  var headers = AlgoliaSearchServer.super_.prototype._computeRequestHeaders.call(this, additionalUA);

  if (this._forward) {
    headers['x-algolia-api-key'] = this._forward.adminAPIKey;
    headers['x-forwarded-for'] = this._forward.endUserIP;
    headers['x-forwarded-api-key'] = this._forward.rateLimitAPIKey;
  }

  if (this._secure) {
    headers['x-algolia-api-key'] = this._secure.apiKey;
    headers['x-algolia-tagfilters'] = this._secure.securityTags;
    headers['x-algolia-usertoken'] = this._secure.userToken;
  }

  return headers;
};
