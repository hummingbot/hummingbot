'use strict'

exports.enter = {
  mathFlow: enterMathFlow,
  mathFlowFenceMeta: enterMathFlowMeta,
  mathText: enterMathText
}
exports.exit = {
  mathFlow: exitMathFlow,
  mathFlowFence: exitMathFlowFence,
  mathFlowFenceMeta: exitMathFlowMeta,
  mathFlowValue: exitMathData,
  mathText: exitMathText,
  mathTextData: exitMathData
}

function enterMathFlow(token) {
  this.enter(
    {
      type: 'math',
      meta: null,
      value: '',
      data: {
        hName: 'div',
        hProperties: {className: ['math', 'math-display']},
        hChildren: [{type: 'text', value: ''}]
      }
    },
    token
  )
}

function enterMathFlowMeta() {
  this.buffer()
}

function exitMathFlowMeta() {
  var data = this.resume()
  this.stack[this.stack.length - 1].meta = data
}

function exitMathFlowFence() {
  // Exit if this is the closing fence.
  if (this.getData('mathFlowInside')) return
  this.buffer()
  this.setData('mathFlowInside', true)
}

function exitMathFlow(token) {
  var data = this.resume().replace(/^(\r?\n|\r)|(\r?\n|\r)$/g, '')
  var node = this.exit(token)
  node.value = data
  node.data.hChildren[0].value = data
  this.setData('mathFlowInside')
}

function enterMathText(token) {
  this.enter(
    {
      type: 'inlineMath',
      value: '',
      data: {
        hName: 'span',
        hProperties: {className: ['math', 'math-inline']},
        hChildren: [{type: 'text', value: ''}]
      }
    },
    token
  )
  this.buffer()
}

function exitMathText(token) {
  var data = this.resume()
  var node = this.exit(token)
  node.value = data
  node.data.hChildren[0].value = data
}

function exitMathData(token) {
  this.config.enter.data.call(this, token)
  this.config.exit.data.call(this, token)
}
