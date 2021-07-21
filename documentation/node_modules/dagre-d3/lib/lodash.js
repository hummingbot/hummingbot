/* global window */

var lodash;

if (typeof require === "function") {
  try {
    lodash = {
      defaults: require("lodash/defaults"),
      each: require("lodash/each"),
      isFunction: require("lodash/isFunction"),
      isPlainObject: require("lodash/isPlainObject"),
      pick: require("lodash/pick"),
      has: require("lodash/has"),
      range: require("lodash/range"),
      uniqueId: require("lodash/uniqueId")
    };
  }
  catch (e) {
    // continue regardless of error
  }
}

if (!lodash) {
  lodash = window._;
}

module.exports = lodash;
