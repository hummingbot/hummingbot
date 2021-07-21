'use strict';

if (process.env.NODE_ENV === "production") {
  module.exports = require("./styled.cjs.prod.js");
} else {
  module.exports = require("./styled.cjs.dev.js");
}
