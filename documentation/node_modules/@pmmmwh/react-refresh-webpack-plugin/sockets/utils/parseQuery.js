/**
 * Parse a query string into an object.
 * @param {string} [querystring] The query string.
 * @returns {Record<string, string>} The parsed query object.
 */
function parseQuery(querystring) {
  let query = '';
  if (typeof querystring === 'string') {
    query = querystring;
  }

  /**
   * Transform query strings such as `?foo1=bar1&foo2=bar2`:
   * - remove `?` from the start
   * - split with `&`
   * - split pairs with `=`
   * The resulting format will be { foo1: 'bar1', foo2: 'bar2' }
   */
  return query
    .replace(/^\?/, '')
    .split('&')
    .reduce(function (acc, entry) {
      const pair = entry.split('=');
      // Add all non-empty entries to the accumulated object
      if (pair[0]) {
        acc[pair[0]] = pair[1];
      }

      return acc;
    }, {});
}

module.exports = parseQuery;
