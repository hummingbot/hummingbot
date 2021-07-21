'use strict';

if (process.env.NODE_ENV === "production") {
  module.exports = require("./weak-memoize.cjs.prod.js");
} else {
  module.exports = require("./weak-memoize.cjs.dev.js");
}
