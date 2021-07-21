'use strict';

if (process.env.NODE_ENV === "production") {
  module.exports = require("./stylis.cjs.prod.js");
} else {
  module.exports = require("./stylis.cjs.dev.js");
}
