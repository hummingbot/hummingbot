"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");

exports.__esModule = true;
exports.validatePageComponent = validatePageComponent;
exports.clearValidationCache = clearValidationCache;

var _path = _interopRequireDefault(require("path"));

var _fsExtra = _interopRequireDefault(require("fs-extra"));

const validationCache = new Set();

function validatePageComponent(page, directory, pluginName) {
  const {
    component
  } = page;

  if (!component) {
    throw new Error(`11322`);
  }

  if (validationCache.has(component)) {
    return {};
  }

  if (!_path.default.isAbsolute(component)) {
    return {
      error: {
        id: `11326`,
        context: {
          pluginName,
          pageObject: page,
          component: component
        }
      },
      message: `${pluginName} must set the absolute path to the page component when create creating a page`
    };
  }

  if (process.env.NODE_ENV !== `test`) {
    if (!_fsExtra.default.existsSync(component)) {
      return {
        error: {
          id: `11325`,
          context: {
            pluginName,
            pageObject: page,
            component: component
          }
        }
      };
    }
  } // Validate that the page component imports React and exports something
  // (hopefully a component).
  //


  if (!component.includes(`/.cache/`) && process.env.NODE_ENV === `production`) {
    const fileContent = _fsExtra.default.readFileSync(component, `utf-8`);

    if (fileContent === ``) {
      const relativePath = _path.default.relative(directory, component);

      return {
        error: {
          id: `11327`,
          context: {
            relativePath
          }
        },
        panicOnBuild: true
      };
    } // this check only applies to js and ts, not mdx


    if ([`.js`, `.jsx`, `.ts`, `.tsx`].includes(_path.default.extname(component))) {
      const includesDefaultExport = fileContent.includes(`export default`) || fileContent.includes(`module.exports`) || fileContent.includes(`exports.default`) || fileContent.includes(`exports["default"]`) || fileContent.match(/export \{.* as default.*\}/s) || fileContent.match(/export \{\s*default\s*\}/s);

      if (!includesDefaultExport) {
        return {
          error: {
            id: `11328`,
            context: {
              fileName: component
            }
          },
          panicOnBuild: true
        };
      }
    }
  }

  validationCache.add(component);
  return {};
}

function clearValidationCache() {
  validationCache.clear();
}
//# sourceMappingURL=validate-page-component.js.map