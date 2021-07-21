'use strict';

if (process.env.NODE_ENV === "production") {
  module.exports = require("./css.cjs.prod.js");
} else {
  module.exports = require("./css.cjs.dev.js");
}
