'use strict'

var stringifyPosition = require('unist-util-stringify-position')
var parseEntities = require('parse-entities')
var serializeCharCode = require('../util/serialize-char-code')
var serializeFormattedCode = require('../util/serialize-formatted-code')
var serializeAbbreviatedTag = require('../util/serialize-abbreviated-tag')
var removePositions = require('../util/remove-positions')
var esIdentifier = require('../util/es-identifier')
var whitespace = require('../util/es-whitespace')
var dedentExpression = require('../util/dedent-expression')

module.exports = parse

var own = {}.hasOwnProperty

var identifierStart = esIdentifier.identifierStart
var identifier = esIdentifier.identifier

var tab = 9 // '\t'
var lineFeed = 10 // '\n'
var space = 32 // ' '
var quotationMark = 34 // '"'
var apostrophe = 39 // "'"
var dash = 45 // '-'
var dot = 46 // '.'
var slash = 47 // '/'
var colon = 58 // ':'
var lessThan = 60 // '<'
var equalsTo = 61 // '='
var greaterThan = 62 // '>'
var graveAccent = 96 // '`'
var leftCurlyBrace = 123 // '{'
var rightCurlyBrace = 125 // '}'
var tilde = 126 // '~'

var suggestionIdentifierStart = 'a letter, `$`, or `_`'
var suggestionIdentifier = 'letters, digits, `$`, or `_`'
var suggestionBeforeAttribute = 'whitespace before attributes'
var suggestionBeforeInitializer = '`=` to initialize a value'
var suggestionValueStart = '`"`, `\'`, or `{`'
var suggestionEnd = 'the end of the tag'
var suggestionTagEnd = '`>` to end the tag'

var parseEntitiesOptions = {nonTerminated: false}

function parse(parser) {
  var proto = parser.prototype
  var spans = proto.inlineTokenizers
  var blocks = proto.blockTokenizers
  var inlineMethods = proto.inlineMethods
  var blockMethods = proto.blockMethods

  // Replace HTML in order with MDX.
  inlineMethods.splice(inlineMethods.indexOf('html'), 1, 'mdx')
  blockMethods.splice(blockMethods.indexOf('html'), 1, 'mdx')
  // Remove indented code and autolinks.
  blockMethods.splice(blockMethods.indexOf('indentedCode'), 1)
  inlineMethods.splice(inlineMethods.indexOf('autoLink'), 1)

  // Replace tokenizers.
  spans.autoLink = undefined
  spans.html = undefined
  spans.mdx = createParser(false)
  blocks.html = undefined
  blocks.indentedCode = undefined
  blocks.mdx = createParser(true)

  // Overwrite paragraph to ignore whitespace around line feeds.
  blocks.paragraph = createParagraphParser(blocks.paragraph)

  // Find tokens fast.
  spans.mdx.locator = locateMdx

  Object.keys(proto).forEach(interrupt)

  function createParser(block) {
    parse.displayName = 'mdx' + (block ? 'Block' : 'Span')
    return parse
    function parse(eat, value, silent) {
      return mdxParser.call(this, eat, value, silent, block)
    }
  }

  function createParagraphParser(oParagraph) {
    return parseParagraph
    function parseParagraph(eat, value, silent) {
      return paragraph.call(this, eat, value, silent, oParagraph)
    }
  }

  function interrupt(key) {
    var prefix = 'interrupt'

    if (key.slice(0, prefix.length) === prefix) {
      proto[key] = proto[key].filter(notHtmlOrIndentedCode)
    }

    function notHtmlOrIndentedCode(tuple) {
      var name = tuple[0]
      return name !== 'html' && name !== 'indentedCode'
    }
  }
}

function mdxParser(eat, value, silent, block) {
  var self = this
  var clean = self.options.position ? noop : removePositions
  var file = self.file
  var index = 0
  var place = Object.assign(eat.now(), {index: index})
  var contentTokenizer = 'tokenize' + (block ? 'Block' : 'Inline')
  var node
  var content

  // Parser state.
  var state = block ? beforeMdxBlock : beforeMdxSpan
  var elementStack = [] // Current open elements.
  var stack = [] // Current open tokens.
  var settled = false
  var crashed = false

  // Shared space.
  var size
  var sizeOpen
  var currentTag

  // Enter adapters.
  var onenter = {
    tag: onentertag,
    closingSlash: onenterclosingslash,
    attributeExpression: onenteranyattribute,
    attributeName: onenteranyattribute,
    selfClosingSlash: onenterselfclosingslash
  }

  // Exit adapters.
  var onexit = {
    closingSlash: onclosingslash,
    primaryName: onprimaryname,
    memberName: onmembername,
    localName: onlocalname,
    name: onname,
    attributeName: onattributename,
    attributeLocalName: onattributelocalname,
    attributeValue: onattributevalue,
    attributeValueExpression: onattributevalueexpression,
    attributeExpression: onattributeexpression,
    selfClosingSlash: onselfclosingslash,
    tag: ontag,
    expression: onexpression
  }

  // Run the state machine.
  main()

  /* istanbul ignore if - used by interruptors, which we’re not using. */
  if (silent) {
    return !crashed
  }

  if (crashed) {
    return
  }

  // Elements have nodes in them.
  // Potentially recursive MDX.
  if (node.type === 'mdxBlockElement' || node.type === 'mdxSpanElement') {
    node.children =
      content.end === undefined
        ? []
        : self[contentTokenizer](slice(content), content.start)
  }
  // Expressions are literal.
  else {
    node.value = dedentExpression(slice(content, 1, 1))
  }

  return eat(value.slice(0, index))(node)

  //
  // State management.
  //

  // Main loop (note that `index` is modified by `consume`).
  function main() {
    /* eslint-disable-next-line no-unmodified-loop-condition */
    while (!settled) {
      state(value.charCodeAt(index))
    }
  }

  // Get the current point.
  function now() {
    return Object.assign({}, place)
  }

  // Clone the current point: note that tokens also have an `index` in their
  // points, refererring to the place in the input string, which we don’t want
  // in the tree.
  function point(source) {
    return {line: source.line, column: source.column, offset: source.offset}
  }

  // Clone the position of a token.
  function position(token) {
    return {start: point(token.start), end: point(token.end)}
  }

  // Move a character forward.
  function consume() {
    // Line ending; assumes CR is not used (remark removes those).
    if (value.charCodeAt(index) === lineFeed) {
      place.line++
      place.column = 1
    }
    // Anything else.
    else {
      place.column++
    }

    index++

    place.offset++
    place.index = index
  }

  // Start a token.
  function enter(type) {
    var token = {type: type, start: now()}

    emit(onenter, token)

    stack.push(token)
  }

  // Stop a token.
  function exit() {
    var token = stack.pop()

    token.end = now()

    emit(onexit, token)
  }

  // Switch to the given state.
  function then(next) {
    state = next
  }

  // Emit a token.
  function emit(adapters, token) {
    if (own.call(adapters, token.type)) {
      adapters[token.type](token)
    }
  }

  // Crash at a nonconforming character.
  function crash(at, expect) {
    var code = value.charCodeAt(index)
    var label
    var base
    var message

    // Non-EOF.
    if (code === code) {
      label = 'character'
      base =
        'Unexpected character ' +
        serializeFormattedCode(code) +
        ' (' +
        serializeCharCode(code) +
        ')'
    }
    // EOF.
    else {
      label = 'eof'
      base = 'Unexpected end of file'
    }

    message = base + ' ' + at + ', expected ' + expect

    fail(message, now(), 'unexpected-' + label)
  }

  function fail(reason, point, label) {
    crashed = true
    settled = true

    /* istanbul ignore else - could be used by plugins. */
    if (!silent) {
      file.fail(reason, point, 'remark-mdx:' + label)
    }
  }

  function slice(token, more, less) {
    return value.slice(
      token.start.index + (more || 0),
      token.end.index - (less || 0)
    )
  }

  //
  // Adapters.
  //

  // Define a new tag node.
  function onentertag() {
    currentTag = {
      type: 'mdxTag',
      name: null,
      close: false,
      selfClosing: false,
      attributes: []
    }
  }

  // Crash if we find an closing tag if there are no elements open.
  function onenterclosingslash() {
    if (elementStack.length === 0) {
      crash('before name', 'an opening tag first as there are no open elements')
    }
  }

  // Crash if we find an attribute on a closing tag.
  function onenteranyattribute() {
    if (currentTag.close) {
      crash(
        'on closing tag after name',
        suggestionEnd + ' instead of attributes on a closing tag'
      )
    }
  }

  // Crash if we find a self-closing closing tag (`</a/>`)
  function onenterselfclosingslash() {
    if (currentTag.close) {
      crash('on closing tag before tag end', suggestionEnd)
    }
  }

  function onclosingslash() {
    currentTag.close = true
  }

  function onprimaryname(token) {
    currentTag.name = slice(token)
  }

  function onmembername(token) {
    currentTag.name += '.' + slice(token)
  }

  function onlocalname(token) {
    currentTag.name += ':' + slice(token)
  }

  // Crash if we find a closing tag that doesn’t match the currently open
  // element.
  function onname() {
    var currentElement = elementStack[elementStack.length - 1]

    // A different element is open.
    if (currentTag.close && currentElement.name !== currentTag.name) {
      fail(
        'Unexpected closing tag `' +
          serializeAbbreviatedTag(currentTag) +
          '`, expected corresponding MDX closing tag for `' +
          serializeAbbreviatedTag(currentElement) +
          '` (' +
          stringifyPosition(currentElement) +
          ')',
        now(),
        'end-tag-mismatch'
      )
    }
  }

  // Add the attribute to the tag.
  function onattributename(token) {
    currentTag.attributes.push({
      type: 'mdxAttribute',
      name: slice(token),
      value: null,
      position: position(token)
    })
  }

  // Change the attribute’s name to include the local name.
  function onattributelocalname(token) {
    var attributes = currentTag.attributes
    var attribute = attributes[attributes.length - 1]

    attribute.name += ':' + slice(token)
    attribute.position.end = point(token.end)
  }

  // Add the attribute value to the attribute.
  function onattributevalue(token) {
    var attributes = currentTag.attributes
    var attribute = attributes[attributes.length - 1]

    attribute.value = parseEntities(slice(token, 1, 1), parseEntitiesOptions)
    attribute.position.end = point(token.end)
  }

  // Add the attribute value to the attribute.
  function onattributevalueexpression(token) {
    var attributes = currentTag.attributes
    var attribute = attributes[attributes.length - 1]

    attribute.value = {
      type: 'mdxValueExpression',
      value: dedentExpression(slice(token, 1, 1)),
      position: position(token)
    }

    attribute.position.end = point(token.end)
  }

  // Add the attribute to the tag.
  function onattributeexpression(token) {
    currentTag.attributes.push({
      type: 'mdxAttributeExpression',
      value: dedentExpression(slice(token, 1, 1)),
      position: position(token)
    })
  }

  // Mark the node as self-closing.
  function onselfclosingslash() {
    currentTag.selfClosing = true
  }

  // Handle the tag.
  function ontag(token) {
    currentTag.position = position(token)

    if (elementStack.length === 0) {
      node = {
        type: 'mdx' + (block ? 'Block' : 'Span') + 'Element',
        name: currentTag.name,
        attributes: currentTag.attributes
      }

      content = {type: 'content', start: token.end}
    }

    // Closing tag (`</x>`).
    if (currentTag.close) {
      clean(elementStack.pop())

      if (elementStack.length === 0) {
        content.end = token.start
      }
    }
    // Self-closing tag (`<x/>`).
    else if (currentTag.selfClosing) {
      clean(currentTag)
    }
    // Opening tag (`<x>`).
    else {
      elementStack.push(currentTag)
    }

    if (elementStack.length === 0) {
      then(block ? afterMdxBlock : afterMdxSpan)
    }
  }

  // Handle the expression.
  function onexpression(token) {
    if (elementStack.length === 0) {
      node = {type: 'mdx' + (block ? 'Block' : 'Span') + 'Expression'}
      content = {type: 'content', start: token.start, end: token.end}
      then(block ? afterMdxBlock : afterMdxSpan)
    }
  }

  //
  // State machine.
  //

  function beforeMdxBlock(code) {
    // In-line Markdown whitespace.
    if (code === tab || code === space) {
      consume()
    }
    // Something else.
    else {
      then(beforeMdxSpan)
    }
  }

  // Start of an expression or element span.
  function beforeMdxSpan(code) {
    // Found our start
    if (code === leftCurlyBrace || code === lessThan) {
      // Reconsume.
      then(data)
    }
    // Something else.
    else {
      crashed = true
      settled = true
    }
  }

  // End of a span.
  function afterMdxSpan() {
    settled = true
  }

  // End of an MDX block.
  function afterMdxBlock(code) {
    // In-line Markdown whitespace.
    if (code === tab || code === space) {
      consume()
    }
    // Found our end!
    else if (code === lineFeed || code !== code) {
      settled = true
    }
    // Something else, not a block.
    else {
      crashed = true
      settled = true
    }
  }

  // Children.
  function data(code) {
    // Start a new tag.
    if (code === lessThan) {
      then(beforeName)
      enter('tag')
      consume()
    }
    // Start a new expression.
    else if (code === leftCurlyBrace) {
      then(expression)
      enter('expression')
      size = 1
      consume()
    }
    // Text.
    else {
      // Reconsume.
      then(text)
      enter('text')
    }
  }

  // Right after `<`, before an optional name.
  function beforeName(code) {
    // Closing tag.
    if (code === slash) {
      then(beforeClosingTagName)
      enter('closingSlash')
      consume()
      exit()
    }
    // Fragment opening tag.
    else if (code === greaterThan) {
      then(data)
      enter('name')
      exit()
      consume()
      exit()
    }
    // Whitespace, remain.
    else if (whitespace(code)) {
      consume()
    }
    // Start of a name.
    else if (identifierStart(code)) {
      then(primaryName)
      enter('name')
      enter('primaryName')
      consume()
    }
    // Exception.
    else {
      crash(
        'before name',
        'a character that can start a name, such as ' +
          suggestionIdentifierStart
      )
    }
  }

  // We’re at the start of a closing tag, right after `</`.
  function beforeClosingTagName(code) {
    // Fragment closing tag.
    if (code === greaterThan) {
      then(data)
      enter('name')
      exit()
      consume()
      exit()
    }
    // Whitespace before name: stay in state.
    else if (whitespace(code)) {
      consume()
    }
    // Start of a closing tag name.
    else if (identifierStart(code)) {
      then(primaryName)
      enter('name')
      enter('primaryName')
      consume()
    }
    // Exception.
    else {
      crash(
        'before name',
        'a character that can start a name, such as ' +
          suggestionIdentifierStart
      )
    }
  }

  // We’re inside the primary name.
  function primaryName(code) {
    // Continuation of name: remain.
    if (code === dash || identifier(code)) {
      consume()
    }
    // End of name.
    else if (
      code === dot ||
      code === slash ||
      code === colon ||
      code === greaterThan ||
      code === leftCurlyBrace ||
      whitespace(code)
    ) {
      then(afterPrimaryName)
      exit()
      // Reconsume.
    }
    // Exception.
    else {
      crash(
        'in name',
        'a name character such as ' +
          suggestionIdentifier +
          '; ' +
          suggestionBeforeAttribute +
          '; or ' +
          suggestionEnd
      )
    }
  }

  // We’re after a name.
  function afterPrimaryName(code) {
    // Start of a member name.
    if (code === dot) {
      then(beforeMemberName)
      consume()
    }
    // Start of a local name.
    else if (code === colon) {
      then(beforeLocalName)
      consume()
    }
    // End of name.
    else if (
      code === slash ||
      code === greaterThan ||
      code === leftCurlyBrace ||
      identifierStart(code)
    ) {
      then(beforeAttribute)
      exit()
      // Reconsume.
    }
    // Remain.
    else if (whitespace(code)) {
      consume()
    }
    // Exception.
    else {
      crash(
        'after name',
        'a character that can start an attribute name, such as ' +
          suggestionIdentifierStart +
          '; ' +
          suggestionBeforeAttribute +
          '; or ' +
          suggestionEnd
      )
    }
  }

  // We’ve seen a `.` and are expecting a member name.
  function beforeMemberName(code) {
    // Start of a member name.
    if (identifierStart(code)) {
      then(memberName)
      enter('memberName')
      consume()
    }
    // Whitespace before member name: stay in state.
    else if (whitespace(code)) {
      consume()
    }
    // Exception.
    else {
      crash(
        'before member name',
        'a character that can start an attribute name, such as ' +
          suggestionIdentifierStart +
          '; ' +
          suggestionBeforeAttribute +
          '; or ' +
          suggestionEnd
      )
    }
  }

  // We’re inside the member name.
  function memberName(code) {
    // Continuation of member name: stay in state
    if (code === dash || identifier(code)) {
      consume()
    }
    // End of member name (note that namespaces and members can’t be combined).
    else if (
      whitespace(code) ||
      code === dot ||
      code === greaterThan ||
      code === slash ||
      code === leftCurlyBrace
    ) {
      then(afterMemberName)
      exit()
      // Reconsume.
    }
    // Exception.
    else {
      crash(
        'in member name',
        'a name character such as ' +
          suggestionIdentifier +
          '; ' +
          suggestionBeforeAttribute +
          '; or ' +
          suggestionEnd
      )
    }
  }

  // We’re after a member name: this is the same as `afterPrimaryName` but we
  // don’t expect colons.
  function afterMemberName(code) {
    // Start another member name.
    if (code === dot) {
      then(beforeMemberName)
      consume()
    }
    // End of name.
    else if (
      code === greaterThan ||
      code === slash ||
      code === leftCurlyBrace ||
      identifierStart(code)
    ) {
      then(beforeAttribute)
      exit()
      // Reconsume.
    }
    // Continue.
    else if (whitespace(code)) {
      consume()
    }
    // Exception.
    else {
      crash(
        'after member name',
        'a character that can start an attribute name, such as ' +
          suggestionIdentifierStart +
          '; ' +
          suggestionBeforeAttribute +
          '; or ' +
          suggestionEnd
      )
    }
  }

  // We’ve seen a `:`, and are expecting a local name.
  function beforeLocalName(code) {
    // Whitespace, stay in state.
    if (whitespace(code)) {
      consume()
    }
    // Start of a local name.
    else if (identifierStart(code)) {
      then(localName)
      enter('localName')
      consume()
    }
    // Exception.
    else {
      crash(
        'before local name',
        'a character that can start a name, such as ' +
          suggestionIdentifierStart
      )
    }
  }

  // We’re inside the local name.
  function localName(code) {
    // Continuation of local name: stay in state
    if (code === dash || identifier(code)) {
      consume()
    }
    // End of local name (note that we don’t expect another colon, or a member).
    else if (
      code === slash ||
      code === greaterThan ||
      code === leftCurlyBrace ||
      whitespace(code)
    ) {
      then(afterLocalName)
      exit()
      exit()
      // Reconsume.
    }
    // Exception.
    else {
      crash(
        'in local name',
        'a name character such as ' +
          suggestionIdentifier +
          '; ' +
          suggestionBeforeAttribute +
          '; or ' +
          suggestionEnd
      )
    }
  }

  // We’re after a local name: this is the same as `afterPrimaryName` but we
  // don’t expect colons or periods.
  function afterLocalName(code) {
    // End of name.
    if (
      code === slash ||
      code === greaterThan ||
      code === leftCurlyBrace ||
      identifierStart(code)
    ) {
      then(beforeAttribute)
      // Reconsume.
    }
    // Continue.
    else if (whitespace(code)) {
      consume()
    }
    // Exception.
    else {
      crash(
        'after local name',
        'a character that can start an attribute name, such as ' +
          suggestionIdentifierStart +
          '; ' +
          suggestionBeforeAttribute +
          '; or ' +
          suggestionEnd
      )
    }
  }

  function beforeAttribute(code) {
    // Mark as self-closing.
    if (code === slash) {
      then(selfClosing)
      enter('selfClosingSlash')
      consume()
      exit()
    }
    // End of tag.
    else if (code === greaterThan) {
      then(data)
      consume()
      exit()
    }
    // Attribute expression.
    else if (code === leftCurlyBrace) {
      then(attributeExpression)
      enter('attributeExpression')
      size = 1
      consume()
    }
    // Whitespace: remain.
    else if (whitespace(code)) {
      consume()
    }
    // Start of an attribute name.
    else if (identifierStart(code)) {
      then(attributeName)
      enter('attributeName')
      consume()
    }
    // Exception.
    else {
      crash(
        'before attribute name',
        'a character that can start an attribute name, such as ' +
          suggestionIdentifierStart +
          '; ' +
          suggestionBeforeAttribute +
          '; or ' +
          suggestionEnd
      )
    }
  }

  // We’re in an attribute expression.
  function attributeExpression(code) {
    // Another opening brace.
    if (code === leftCurlyBrace) {
      size++
      consume()
    }
    // A closing brace.
    else if (code === rightCurlyBrace) {
      // Done.
      if (size === 1) {
        then(beforeAttribute)
        size = undefined
        consume()
        exit()
      }
      // Continue.
      else {
        size--
        consume()
      }
    }
    // Continuation.
    else if (code === code) {
      consume()
    }
    // Exception (EOF).
    else {
      crash('in attribute expression', 'a corresponding closing brace for `{`')
    }
  }

  // We’re right after the first character of an attribute.
  function attributeName(code) {
    // Continuation of the attribute name.
    if (code === dash || identifier(code)) {
      consume()
    }
    // End of attribute name or tag.
    else if (
      code === colon ||
      code === equalsTo ||
      code === greaterThan ||
      code === slash ||
      code === leftCurlyBrace ||
      whitespace(code)
    ) {
      // Reconsume.
      then(afterAttributeName)
      exit()
    }
    // Exception.
    else {
      crash(
        'in attribute name',
        'an attribute name character such as ' +
          suggestionIdentifier +
          '; ' +
          suggestionBeforeInitializer +
          '; ' +
          suggestionBeforeAttribute +
          '; or ' +
          suggestionEnd
      )
    }
  }

  // We’re after an attribute name, probably finding an equals.
  function afterAttributeName(code) {
    // Start of a local name.
    if (code === colon) {
      then(beforeAttributeLocalName)
      consume()
    }
    // Start of an attribute value.
    else if (code === equalsTo) {
      then(beforeAttributeValue)
      consume()
    }
    // End of tag / new attribute.
    else if (
      code === greaterThan ||
      code === slash ||
      code === leftCurlyBrace ||
      identifierStart(code)
    ) {
      // Reconsume.
      then(beforeAttribute)
    }
    // Continuation.
    else if (whitespace(code)) {
      consume()
    }
    // Exception.
    else {
      crash(
        'after attribute name',
        'a character that can start an attribute name, such as ' +
          suggestionIdentifierStart +
          '; ' +
          suggestionBeforeInitializer +
          '; or ' +
          suggestionEnd
      )
    }
  }

  // We’ve seen a `:`, and are expecting a local name.
  function beforeAttributeLocalName(code) {
    // Start of a local name.
    if (identifierStart(code)) {
      then(attributeLocalName)
      enter('attributeLocalName')
      consume()
    }
    // Whitespace, stay in state.
    else if (whitespace(code)) {
      consume()
    }
    // Exception.
    else {
      crash(
        'before local attribute name',
        'a character that can start an attribute name, such as ' +
          suggestionIdentifierStart +
          '; ' +
          suggestionBeforeInitializer +
          '; or ' +
          suggestionEnd
      )
    }
  }

  // We’re right after the first character of a local attribute name.
  function attributeLocalName(code) {
    // Continuation of the local attribute name.
    if (code === dash || identifier(code)) {
      consume()
    }
    // End of tag / attribute name.
    else if (
      code === slash ||
      code === equalsTo ||
      code === greaterThan ||
      code === leftCurlyBrace ||
      whitespace(code)
    ) {
      // Reconsume.
      then(afterAttributeLocalName)
      exit()
    }
    // Exception.
    else {
      crash(
        'in local attribute name',
        'an attribute name character such as ' +
          suggestionIdentifier +
          '; ' +
          suggestionBeforeInitializer +
          '; ' +
          suggestionBeforeAttribute +
          '; or ' +
          suggestionEnd
      )
    }
  }

  // We’re after a local attribute name, expecting an equals.
  function afterAttributeLocalName(code) {
    // Start of an attribute value.
    if (code === equalsTo) {
      then(beforeAttributeValue)
      consume()
    }
    // End of tag / new attribute.
    else if (
      code === slash ||
      code === greaterThan ||
      code === leftCurlyBrace ||
      identifierStart(code)
    ) {
      // Reconsume.
      then(beforeAttribute)
    }
    // Continuation.
    else if (whitespace(code)) {
      consume()
    }
    // Exception.
    else {
      crash(
        'after local attribute name',
        'a character that can start an attribute name, such as ' +
          suggestionIdentifierStart +
          '; ' +
          suggestionBeforeInitializer +
          '; or ' +
          suggestionEnd
      )
    }
  }

  // We’re after an attribute value, expecting quotes and such.
  function beforeAttributeValue(code) {
    // Start of double quoted value.
    if (code === quotationMark) {
      then(attributeValueDoubleQuoted)
      enter('attributeValue')
      consume()
    }
    // Start of quoted value.
    else if (code === apostrophe) {
      then(attributeValueSingleQuoted)
      enter('attributeValue')
      consume()
    }
    // Start of an assignment expression.
    else if (code === leftCurlyBrace) {
      then(attributeValueExpression)
      enter('attributeValueExpression')
      size = 1
      consume()
    }
    // Continuation.
    else if (whitespace(code)) {
      consume()
    }
    // Exception.
    else {
      crash(
        'before attribute value',
        'a character that can start an attribute value, such as ' +
          suggestionValueStart
      )
    }
  }

  // We’re in a double quoted attribute value.
  function attributeValueDoubleQuoted(code) {
    // Done.
    if (code === quotationMark) {
      then(beforeAttribute)
      consume()
      exit()
    }
    // Continuation.
    else if (code === code) {
      consume()
    }
    // Exception (EOF).
    else {
      crash('in attribute value', 'a corresponding closing quote `"`')
    }
  }

  // We’re in a single quoted attribute value.
  function attributeValueSingleQuoted(code) {
    // Done.
    if (code === apostrophe) {
      then(beforeAttribute)
      consume()
      exit()
    }
    // Continuation.
    else if (code === code) {
      consume()
    }
    // Exception (EOF).
    else {
      crash('in attribute value', "a corresponding closing quote `'`")
    }
  }

  // We’re in a attribute value assignment expression.
  function attributeValueExpression(code) {
    // Another opening brance.
    if (code === leftCurlyBrace) {
      size++
      consume()
    }
    // A closing brace.
    else if (code === rightCurlyBrace) {
      // Done.
      if (size === 1) {
        size = undefined
        then(beforeAttribute)
        consume()
        exit()
      }
      // Continue.
      else {
        size--
        consume()
      }
    }
    // Continuation.
    else if (code === code) {
      consume()
    }
    // Exception (EOF).
    else {
      crash(
        'in attribute value expression',
        'a corresponding closing brace for `{`'
      )
    }
  }

  // Right after the slash on a name, e.g., `<asd /`.
  function selfClosing(code) {
    // End of tag.
    if (code === greaterThan) {
      then(data)
      consume()
      exit()
    }
    // Whitespace.
    else if (whitespace(code)) {
      consume()
    }
    // Exception.
    else {
      crash('after self-closing slash', suggestionTagEnd)
    }
  }

  // Nested expression.
  function expression(code) {
    // Another opening brace.
    if (code === leftCurlyBrace) {
      size++
      consume()
    }
    // A closing brace.
    else if (code === rightCurlyBrace) {
      // Done.
      if (size === 1) {
        then(data)
        size = undefined
        consume()
        exit()
      }
      // Continue.
      else {
        size--
        consume()
      }
    }
    // Continuation.
    else if (code === code) {
      consume()
    }
    // Exception (EOF).
    else {
      crash('in expression', 'a corresponding closing brace for `{`')
    }
  }

  // Text.
  function text(code) {
    var currentElement

    // Note: the JSX spec defines `> and `}` on their own in text as incorrect.
    // Acorn does conform but Babel doesn’t.
    // We don’t conform either, as Markdown uses `>` is for block quotes, and
    // it would prevent their use in JSX.

    // Data.
    if (code === lessThan || code === leftCurlyBrace) {
      // Reconsume.
      then(data)
      exit()
    }
    // Skip code spans and fenced code block.
    else if (code === graveAccent) {
      then(accentQuotedOpen)
      sizeOpen = 1
      consume()
    }
    // Skip code spans and fenced code block.
    else if (code === tilde) {
      then(tildeQuotedOpen)
      sizeOpen = 1
      consume()
    }
    // Text.
    else if (code === code) {
      consume()
    }
    // Exception (EOF).
    else {
      currentElement = elementStack[elementStack.length - 1]
      crash(
        'in element',
        'a corresponding MDX closing tag for `' +
          serializeAbbreviatedTag(currentElement) +
          '` (' +
          stringifyPosition(currentElement) +
          ')'
      )
    }
  }

  // Inside ticks.
  function accentQuotedOpen(code) {
    // More.
    if (code === graveAccent) {
      sizeOpen++
      consume()
    }
    // Character.
    else if (code === code) {
      then(accentQuoted)
      consume()
    }
    // EOF.
    else {
      crash('in code', 'a corresponding fence for `` ` ``')
    }
  }

  // In tick quoted value.
  function accentQuoted(code) {
    // Closing fence?
    if (code === graveAccent) {
      then(accentQuotedClose)
      size = 1
      consume()
    }
    // Character.
    else if (code === code) {
      consume()
    }
    // EOF.
    else {
      crash('in code', 'a corresponding fence for `` ` ``')
    }
  }

  // Closing fence?
  function accentQuotedClose(code) {
    // More.
    if (code === graveAccent) {
      size++
      consume()
    }
    // Anything else.
    else {
      // Done!
      if (size === sizeOpen) {
        then(text)
        sizeOpen = undefined
        size = undefined
        // Reconsume
      }
      // Nope.
      else {
        then(accentQuoted)
        size = undefined
        // Reconsume
      }
    }
  }

  // Inside tildes.
  function tildeQuotedOpen(code) {
    // More.
    if (code === tilde) {
      consume()
      sizeOpen++
    }
    // Non-EOF.
    else if (code === code) {
      then(tildeQuoted)
      consume()
    }
    // EOF.
    else {
      crash('in code', 'a corresponding fence for `~`')
    }
  }

  // In tick quoted value.
  function tildeQuoted(code) {
    // Closing?
    if (code === tilde) {
      then(tildeQuotedClose)
      consume()
      size = 1
    }
    // Non-EOF.
    else if (code === code) {
      consume()
    }
    // EOF.
    else {
      crash('in code', 'a corresponding fence for `~`')
    }
  }

  // Closing?
  function tildeQuotedClose(code) {
    // More.
    if (code === tilde) {
      consume()
      size++
    }
    // Anything else.
    else {
      // Done!
      if (size === sizeOpen) {
        then(text)
        sizeOpen = undefined
        size = undefined
        // Reconsume
      }
      // Nope.
      else {
        then(tildeQuoted)
        size = undefined
        // Reconsume
      }
    }
  }
}

function paragraph(eat, value, silent, oParagraph) {
  var start = /^[ \t\n]+/
  var end = /[ \t\n]+$/
  var between = /[ \t]*\n[ \t]*/g
  var result = oParagraph.call(this, eat, value, silent)

  /* istanbul ignore else - paragraph is currently last, so essentially always
   * matches. */
  if (result && result.type) {
    cleanWhitespace(result, true, true)
  }

  return result

  function cleanWhitespace(node, atStart, atEnd) {
    if (node.type === 'text') {
      return cleanText(node, atStart, atEnd)
    }

    if (node.children) {
      return cleanAll(node, atStart, atEnd)
    }

    return false
  }

  function cleanAll(node, atStart, atEnd) {
    var children = node.children
    var length = children.length
    var index = -1
    var start = atStart
    var child

    while (++index < length) {
      child = children[index]

      start = cleanWhitespace(
        child,
        start,
        index === length - 1 ? atEnd : false
      )

      if (child.type === 'text' && child.value.length === 0) {
        children.splice(index, 1)
        index--
        length--
      }
    }

    // Types of `paragraph` and its children (phrasing content) that *do not*
    // have markers at their end.
    // If we do have markers, it doesn’t matter whether we ended in a newline.
    return node.type === 'paragraph' || node.type === 'text' ? start : false
  }

  function cleanText(node, atStart, atEnd) {
    var value = node.value.replace(between, '\n')

    if (atStart) value = value.replace(start, '')
    if (atEnd) value = value.replace(end, '')

    node.value = value

    return value ? value.charCodeAt(value.length - 1) === lineFeed : atStart
  }
}

function locateMdx(value, from) {
  var brace = value.indexOf('{', from)
  var angle = value.indexOf('<', from)
  return angle === -1 ? brace : brace === -1 ? angle : Math.min(brace, angle)
}

function noop() {}
