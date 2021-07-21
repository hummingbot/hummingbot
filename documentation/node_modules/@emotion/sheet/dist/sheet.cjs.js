'use strict';

if (process.env.NODE_ENV === "production") {
  module.exports = require("./sheet.cjs.prod.js");
} else {
  module.exports = require("./sheet.cjs.dev.js");
}
