'use strict';

if (process.env.NODE_ENV === "production") {
  module.exports = require("./serialize.cjs.prod.js");
} else {
  module.exports = require("./serialize.cjs.dev.js");
}
