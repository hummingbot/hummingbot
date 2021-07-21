global.options = {
  cache: {
    content: {
      // testing an arbitrary string can be passed through to override
      // the header value, YES the misspellings are intentional
      cacheControl: 'pubic, marx-aged=-100'
    }
  }
}

// otherwise just the same as basic.
require('./basic.js')
