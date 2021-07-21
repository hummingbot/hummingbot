
'use strict'

if (process.env.NODE_ENV === 'production') {
  module.exports = require('./observe-rect.cjs.production.min.js')
} else {
  module.exports = require('./observe-rect.cjs.development.js')
}
