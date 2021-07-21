'use strict'

module.exports = createMathHtmlExtension

var katex = require('katex')

function createMathHtmlExtension(options) {
  return {
    enter: {
      mathFlow: onentermathflow,
      mathFlowFenceMeta: onentermathflowmeta,
      mathText: onentermathtext
    },
    exit: {
      mathFlow: onexitmathflow,
      mathFlowFence: onexitmathfencedfence,
      mathFlowFenceMeta: onexitmathflowmeta,
      mathFlowValue: onexitmathdata,
      mathText: onexitmathtext,
      mathTextData: onexitmathdata
    }
  }

  function onentermathflow() {
    this.lineEndingIfNeeded()
    this.tag('<div class="math math-display">')
  }

  function onentermathflowmeta() {
    this.buffer()
  }

  function onexitmathflowmeta() {
    this.resume()
  }

  function onexitmathfencedfence() {
    // After the first fence.
    if (!this.getData('mathFlowOpen')) {
      this.setData('mathFlowOpen', true)
      this.setData('slurpOneLineEnding', true)
      this.buffer()
    }
  }

  function onexitmathflow() {
    var value = this.resume()
    this.tag(math(value.replace(/(?:\r?\n|\r)$/, ''), true))
    this.tag('</div>')
    this.setData('mathFlowOpen')
    this.setData('slurpOneLineEnding')
  }

  function onentermathtext() {
    // Double?
    this.tag('<span class="math math-inline">')
    this.buffer()
  }

  function onexitmathtext() {
    var value = this.resume()
    this.tag(math(value, false))
    this.tag('</span>')
  }

  function onexitmathdata(token) {
    this.raw(this.sliceSerialize(token))
  }

  function math(value, displayMode) {
    return katex.renderToString(
      value,
      Object.assign({}, options, {displayMode: displayMode})
    )
  }
}
