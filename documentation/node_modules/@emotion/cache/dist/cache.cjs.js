'use strict';

if (process.env.NODE_ENV === "production") {
  module.exports = require("./cache.cjs.prod.js");
} else {
  module.exports = require("./cache.cjs.dev.js");
}
