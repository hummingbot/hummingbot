'use strict';

if (process.env.NODE_ENV === "production") {
  module.exports = require("./memoize.cjs.prod.js");
} else {
  module.exports = require("./memoize.cjs.dev.js");
}
