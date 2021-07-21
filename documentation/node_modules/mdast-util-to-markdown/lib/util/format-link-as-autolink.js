module.exports = formatLinkAsAutolink

var toString = require('mdast-util-to-string')

function formatLinkAsAutolink(node) {
  var raw = toString(node)

  return (
    // If there’s a url…
    node.url &&
    // And there’s a no title…
    !node.title &&
    // And if the url is the same as the content…
    (raw === node.url || 'mailto:' + raw === node.url) &&
    // And that starts w/ a protocol…
    /^[a-z][a-z+.-]+:/i.test(node.url) &&
    // And that doesn’t contain ASCII control codes (character escapes and
    // references don’t work) or angle brackets…
    !/[\0- <>\u007F]/.test(node.url)
  )
}
