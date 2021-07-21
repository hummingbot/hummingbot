'use strict'

exports.tokenize = tokenizeMathFenced
exports.concrete = true

var prefixSize = require('micromark/dist/util/prefix-size')
var createSpace = require('micromark/dist/tokenize/factory-space')

function tokenizeMathFenced(effects, ok, nok) {
  var self = this
  var initialPrefix = prefixSize(this.events, 'linePrefix')
  var sizeOpen = 0

  return start

  function start(code) {
    /* istanbul ignore if - handled by mm */
    if (code !== 36) throw new Error('expected `$`')

    effects.enter('mathFlow')
    effects.enter('mathFlowFence')
    effects.enter('mathFlowFenceSequence')
    return sequenceOpen(code)
  }

  function sequenceOpen(code) {
    if (code === 36) {
      effects.consume(code)
      sizeOpen++
      return sequenceOpen
    }

    effects.exit('mathFlowFenceSequence')
    return sizeOpen < 2
      ? nok(code)
      : createSpace(effects, metaOpen, 'whitespace')(code)
  }

  function metaOpen(code) {
    if (code === null || code === -5 || code === -4 || code === -3) {
      return openAfter(code)
    }

    effects.enter('mathFlowFenceMeta')
    effects.enter('chunkString', {contentType: 'string'})
    return meta(code)
  }

  function meta(code) {
    if (code === null || code === -5 || code === -4 || code === -3) {
      effects.exit('chunkString')
      effects.exit('mathFlowFenceMeta')
      return openAfter(code)
    }

    if (code === 36) return nok(code)
    effects.consume(code)
    return meta
  }

  function openAfter(code) {
    effects.exit('mathFlowFence')
    return self.interrupt ? ok(code) : content(code)
  }

  function content(code) {
    if (code === null) {
      return after(code)
    }

    if (code === -5 || code === -4 || code === -3) {
      effects.enter('lineEnding')
      effects.consume(code)
      effects.exit('lineEnding')
      return effects.attempt(
        {tokenize: tokenizeClosingFence, partial: true},
        after,
        initialPrefix
          ? createSpace(effects, content, 'linePrefix', initialPrefix + 1)
          : content
      )
    }

    effects.enter('mathFlowValue')
    return contentContinue(code)
  }

  function contentContinue(code) {
    if (code === null || code === -5 || code === -4 || code === -3) {
      effects.exit('mathFlowValue')
      return content(code)
    }

    effects.consume(code)
    return contentContinue
  }

  function after(code) {
    effects.exit('mathFlow')
    return ok(code)
  }

  function tokenizeClosingFence(effects, ok, nok) {
    var size = 0

    return createSpace(effects, closingPrefixAfter, 'linePrefix', 4)

    function closingPrefixAfter(code) {
      effects.enter('mathFlowFence')
      effects.enter('mathFlowFenceSequence')
      return closingSequence(code)
    }

    function closingSequence(code) {
      if (code === 36) {
        effects.consume(code)
        size++
        return closingSequence
      }

      if (size < sizeOpen) return nok(code)
      effects.exit('mathFlowFenceSequence')
      return createSpace(effects, closingSequenceEnd, 'whitespace')(code)
    }

    function closingSequenceEnd(code) {
      if (code === null || code === -5 || code === -4 || code === -3) {
        effects.exit('mathFlowFence')
        return ok(code)
      }

      return nok(code)
    }
  }
}
