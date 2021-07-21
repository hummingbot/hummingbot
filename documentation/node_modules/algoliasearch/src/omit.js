module.exports = function omit(obj, test) {
  var keys = require('object-keys');
  var foreach = require('foreach');

  var filtered = {};

  foreach(keys(obj), function doFilter(keyName) {
    if (test(keyName) !== true) {
      filtered[keyName] = obj[keyName];
    }
  });

  return filtered;
};
