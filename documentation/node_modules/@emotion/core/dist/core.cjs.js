'use strict';

if (process.env.NODE_ENV === "production") {
  module.exports = require("./core.cjs.prod.js");
} else {
  module.exports = require("./core.cjs.dev.js");
}
