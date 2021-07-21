'use strict';

if (process.env.NODE_ENV === "production") {
  module.exports = require("./babel-plugin-emotion.cjs.prod.js");
} else {
  module.exports = require("./babel-plugin-emotion.cjs.dev.js");
}
