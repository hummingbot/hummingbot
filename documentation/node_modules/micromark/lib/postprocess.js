module.exports = postprocess

var subtokenize = require('./util/subtokenize')

function postprocess(events) {
  while (!subtokenize(events)) {
    // Empty
  }

  return events
}
