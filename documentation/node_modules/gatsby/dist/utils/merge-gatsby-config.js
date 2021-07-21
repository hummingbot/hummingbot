"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");

exports.__esModule = true;
exports.mergeGatsbyConfig = void 0;

var _lodash = _interopRequireDefault(require("lodash"));

/**
 * Normalize plugin spec before comparing so
 *  - `gatsby-plugin-name`
 *  - { resolve: `gatsby-plugin-name` }
 *  - { resolve: `gatsby-plugin-name`, options: {} }
 * are all considered equal
 */
const normalizePluginEntry = entry => _lodash.default.isString(entry) ? {
  resolve: entry,
  options: {}
} : _lodash.default.isObject(entry) ? {
  options: {},
  ...entry
} : entry;

const howToMerge = {
  /**
   * pick a truthy value by default.
   * This makes sure that if a single value is defined, that one it used.
   * We prefer the "right" value, because the user's config will be "on the right"
   */
  byDefault: (a, b) => b || a,
  siteMetadata: (objA, objB) => _lodash.default.merge({}, objA, objB),
  // plugins are concatenated and uniq'd, so we don't get two of the same plugin value
  plugins: (a = [], b = []) => _lodash.default.uniqWith(a.concat(b), (a, b) => _lodash.default.isEqual(_lodash.default.pick(normalizePluginEntry(a), [`resolve`, `options`]), _lodash.default.pick(normalizePluginEntry(b), [`resolve`, `options`]))),
  mapping: (objA, objB) => _lodash.default.merge({}, objA, objB)
};
/**
 * Defines how a theme object is merged with the user's config
 */

const mergeGatsbyConfig = (a, b) => {
  // a and b are gatsby configs, If they have keys, that means there are values to merge
  const allGatsbyConfigKeysWithAValue = _lodash.default.uniq(Object.keys(a).concat(Object.keys(b))); // reduce the array of mergable keys into a single gatsby config object


  const mergedConfig = allGatsbyConfigKeysWithAValue.reduce((config, gatsbyConfigKey) => {
    // choose a merge function for the config key if there's one defined,
    // otherwise use the default value merge function
    const mergeFn = howToMerge[gatsbyConfigKey] || howToMerge.byDefault;
    return { ...config,
      [gatsbyConfigKey]: mergeFn(a[gatsbyConfigKey], b[gatsbyConfigKey])
    };
  }, {}); // return the fully merged config

  return mergedConfig;
};

exports.mergeGatsbyConfig = mergeGatsbyConfig;
//# sourceMappingURL=merge-gatsby-config.js.map