'use strict';

if (process.env.NODE_ENV === "production") {
  module.exports = require("./is-prop-valid.cjs.prod.js");
} else {
  module.exports = require("./is-prop-valid.cjs.dev.js");
}
