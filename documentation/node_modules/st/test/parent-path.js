const path = require('path')

global.options = {
  path: path.dirname(__filename) + '/..'
}

// otherwise just the same as basic.
require('./basic.js')
