"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");

exports.__esModule = true;
exports.printDeprecationWarnings = printDeprecationWarnings;

var _fs = _interopRequireDefault(require("fs"));

var _glob = _interopRequireDefault(require("glob"));

var _chalk = _interopRequireDefault(require("chalk"));

function printDeprecationWarnings() {
  const deprecatedApis = [`boundActionCreators`, `pathContext`];
  const fixMap = {
    boundActionCreators: {
      newName: `actions`,
      docsLink: `https://gatsby.dev/boundActionCreators`
    },
    pathContext: {
      newName: `pageContext`,
      docsLink: `https://gatsby.dev/pathContext`
    }
  };
  const deprecatedLocations = {
    boundActionCreators: [],
    pathContext: []
  };

  _glob.default.sync(`{,!(node_modules|public)/**/}*.js`, {
    nodir: true
  }).forEach(file => {
    const fileText = _fs.default.readFileSync(file);

    const matchingApis = deprecatedApis.filter(api => fileText.includes(api));
    matchingApis.forEach(api => deprecatedLocations[api].push(file));
  });

  deprecatedApis.forEach(api => {
    if (deprecatedLocations[api].length) {
      console.log(`%s %s %s %s`, _chalk.default.cyan(api), _chalk.default.yellow(`is deprecated. Please use`), _chalk.default.cyan(fixMap[api].newName), _chalk.default.yellow(`instead. For migration instructions, see ${fixMap[api].docsLink}\nCheck the following files:`));
      console.log();
      deprecatedLocations[api].forEach(file => console.log(file));
      console.log();
    }
  });
}
//# sourceMappingURL=print-deprecation-warnings.js.map