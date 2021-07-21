'use strict';

if (process.env.NODE_ENV === "production") {
  module.exports = require("./styled-base.cjs.prod.js");
} else {
  module.exports = require("./styled-base.cjs.dev.js");
}
