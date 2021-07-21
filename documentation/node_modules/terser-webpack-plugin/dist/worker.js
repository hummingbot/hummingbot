"use strict";

const minify = require('./minify');

function transform(options) {
  // 'use strict' => this === undefined (Clean Scope)
  // Safer for possible security issues, albeit not critical at all here
  // eslint-disable-next-line no-new-func, no-param-reassign
  options = new Function('exports', 'require', 'module', '__filename', '__dirname', `'use strict'\nreturn ${options}`)(exports, require, module, __filename, __dirname);
  const result = minify(options);

  if (result.error) {
    throw result.error;
  } else {
    return result;
  }
}

module.exports.transform = transform;