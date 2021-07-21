"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");

exports.__esModule = true;
exports.default = mapTemplatesToStaticQueryHashes;

var _lodash = require("lodash");

var _path = _interopRequireDefault(require("path"));

var _gatsbyCoreUtils = require("gatsby-core-utils");

/* When we traverse upwards, we need to know where to stop. We'll call these terminal nodes.
 * `async-requires.js` is the entry point for every page, while `api-runner-browser-plugins.js`
 * is the one for `gatsby-browser` (where one would use wrapRootElement or wrapPageElement APIs)
 */
const entryNodes = [`.cache/api-runner-browser-plugins.js`, `.cache/_this_is_virtual_fs_path_/$virtual/async-requires.js`];
/* This function takes the current Redux state and a compilation
 * object from webpack and returns a map of unique templates
 * to static queries included in each (as hashes).
 *
 * This isn't super straightforward because templates may include
 * deep component trees with static queries present at any depth.
 * This is why it is necessary to map templates to all their (user land and node_modules)
 * dependencies first and then map those dependencies to known static queries.
 *
 * Also, Gatsby makes it possible to wrap an entire site or page with a layout
 * or other component(s) via the wrapRootElement and wrapPageElement APIs. These must
 * also be handled when computing static queries for a page.
 *
 * Let's go through the implementation step by step.
 */

function mapTemplatesToStaticQueryHashes(reduxState, compilation) {
  /* The `staticQueryComponents` slice of state is useful because
   * it is a pre extracted collection of all static queries found in a Gatsby site.
   * This lets us traverse upwards from those to templates that
   * may contain components that contain them.
   * Note that this upward traversal is much shallower (and hence more performant)
   * than an equivalent downward one from an entry point.
   */
  const {
    components,
    staticQueryComponents
  } = reduxState;
  const {
    modules
  } = compilation;
  /* We call the queries included above a page (via wrapRootElement or wrapPageElement APIs)
   * global queries. For now, we include these in every single page for simplicity. Overhead
   * here is not much since we are storing hashes (that reference separate result files)
   * as opposed to inlining results. We may move these to app-data perhaps in the future.
   */

  const globalStaticQueries = new Set();
  /* This function takes a webpack module corresponding
   * to the file containing a static query and returns
   * a Set of strings, each an absolute path of a dependent
   * of this module
   */

  function getDeps(mod) {
    const staticQueryModuleComponentPath = mod.resource;
    const result = new Set();
    const seen = new Set(staticQueryModuleComponentPath ? [staticQueryModuleComponentPath] : []); // This is the body of the recursively called function

    function getDepsRec(m, seen) {
      // Reasons in webpack are literally reasons of why this module was included in the tree
      const hasReasons = m.hasReasons(); // Is this node one of our known terminal nodes? See explanation above

      const isEntryNode = entryNodes.some(entryNode => {
        var _m$resource;

        return m === null || m === void 0 ? void 0 : (_m$resource = m.resource) === null || _m$resource === void 0 ? void 0 : _m$resource.includes(entryNode);
      }); // Exit if we don't have any reasons or we have reached a possible terminal node

      if (!hasReasons || isEntryNode) {
        return result;
      } // These are non terminal dependents and hence modules that need
      // further upward traversal


      const nonTerminalDependents = m.reasons.filter(r => {
        const dependentModule = r.module;
        const isTerminal = entryNodes.some(entryNode => {
          var _dependentModule$reso;

          return dependentModule === null || dependentModule === void 0 ? void 0 : (_dependentModule$reso = dependentModule.resource) === null || _dependentModule$reso === void 0 ? void 0 : _dependentModule$reso.includes(entryNode);
        });
        return !isTerminal;
      }).map(r => r.module).filter(Boolean).filter(r => !r.resource || !seen.has(r.resource));
      const uniqDependents = (0, _lodash.uniqBy)(nonTerminalDependents, d => d === null || d === void 0 ? void 0 : d.identifier());

      for (const uniqDependent of uniqDependents) {
        if (uniqDependent.resource) {
          result.add((0, _gatsbyCoreUtils.slash)(uniqDependent.resource)); // Queries used in gatsby-browser are global and should be added to all pages

          if (isGatsbyBrowser(uniqDependent)) {
            if (staticQueryModuleComponentPath) {
              globalStaticQueries.add((0, _gatsbyCoreUtils.slash)(staticQueryModuleComponentPath));
            }
          } else {
            seen.add(uniqDependent.resource);
          }
        }

        getDepsRec(uniqDependent, seen);
      }

      return result;
    }

    return getDepsRec(mod, seen);
  }

  const mapOfStaticQueryComponentsToDependants = new Map(); // For every known static query, we get its dependents.

  staticQueryComponents.forEach(({
    componentPath
  }) => {
    // componentPaths are slashed by gatsby-core-utils we undo it
    const nonSlashedPath = _path.default.resolve(componentPath);

    const staticQueryComponentModule = modules.find(m => m.resource === nonSlashedPath);
    const dependants = staticQueryComponentModule ? getDeps(staticQueryComponentModule) : new Set();
    mapOfStaticQueryComponentsToDependants.set(componentPath, dependants);
  });
  const mapOfComponentsToStaticQueryHashes = mapComponentsToStaticQueryHashes(staticQueryComponents);
  const globalStaticQueryHashes = [];
  globalStaticQueries.forEach(q => {
    const hash = mapOfComponentsToStaticQueryHashes.get(q);

    if (hash) {
      globalStaticQueryHashes.push(hash);
    }
  }); // For every known page, we get queries

  const mapOfTemplatesToStaticQueryHashes = new Map();
  components.forEach(page => {
    const staticQueryHashes = [...globalStaticQueryHashes]; // Does this page contain an inline static query?

    if (mapOfComponentsToStaticQueryHashes.has(page.componentPath)) {
      const hash = mapOfComponentsToStaticQueryHashes.get(page.componentPath);

      if (hash) {
        staticQueryHashes.push(hash);
      }
    } // Check dependencies


    mapOfStaticQueryComponentsToDependants.forEach((setOfDependants, staticQueryComponentPath) => {
      if (setOfDependants.has(page.componentPath)) {
        const hash = mapOfComponentsToStaticQueryHashes.get(staticQueryComponentPath);

        if (hash) {
          staticQueryHashes.push(hash);
        }
      }
    });
    mapOfTemplatesToStaticQueryHashes.set(page.componentPath, staticQueryHashes.sort().map(String));
  });
  return mapOfTemplatesToStaticQueryHashes;
}

function mapComponentsToStaticQueryHashes(staticQueryComponents) {
  const map = new Map();
  staticQueryComponents.forEach(({
    componentPath,
    hash
  }) => {
    map.set(componentPath, hash);
  });
  return map;
}

function isGatsbyBrowser(m) {
  var _m$resource2;

  return !!(m === null || m === void 0 ? void 0 : (_m$resource2 = m.resource) === null || _m$resource2 === void 0 ? void 0 : _m$resource2.includes(`gatsby-browser.js`));
}
//# sourceMappingURL=map-templates-to-static-query-hashes.js.map