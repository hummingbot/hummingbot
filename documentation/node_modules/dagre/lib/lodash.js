/* global window */

var lodash;

if (typeof require === "function") {
  try {
    lodash = {
      cloneDeep: require("lodash/cloneDeep"),
      constant: require("lodash/constant"),
      defaults: require("lodash/defaults"),
      each: require("lodash/each"),
      filter: require("lodash/filter"),
      find: require("lodash/find"),
      flatten: require("lodash/flatten"),
      forEach: require("lodash/forEach"),
      forIn: require("lodash/forIn"),
      has:  require("lodash/has"),
      isUndefined: require("lodash/isUndefined"),
      last: require("lodash/last"),
      map: require("lodash/map"),
      mapValues: require("lodash/mapValues"),
      max: require("lodash/max"),
      merge: require("lodash/merge"),
      min: require("lodash/min"),
      minBy: require("lodash/minBy"),
      now: require("lodash/now"),
      pick: require("lodash/pick"),
      range: require("lodash/range"),
      reduce: require("lodash/reduce"),
      sortBy: require("lodash/sortBy"),
      uniqueId: require("lodash/uniqueId"),
      values: require("lodash/values"),
      zipObject: require("lodash/zipObject"),
    };
  } catch (e) {
    // continue regardless of error
  }
}

if (!lodash) {
  lodash = window._;
}

module.exports = lodash;
