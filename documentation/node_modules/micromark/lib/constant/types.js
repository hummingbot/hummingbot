// This module is compiled away!
//
// Here is the list of all types of tokens exposed by micromark, with a short
// explanation of what they include and where they are found.
// In picking names, generally, the rule is to be as explicit as possible
// instead of reusing names.
// For example, there is a `definitionDestination` and a `resourceDestination`,
// instead of one shared name.

// Generic type for data, such as in a title, a destination, etc.
exports.data = 'data'

// Generic type for syntactic whitespace (tabs, virtual spaces, spaces).
// Such as, between a fenced code fence and an info string.
exports.whitespace = 'whitespace'

// Generic type for line endings (line feed, carriage return, carriage return +
// line feed).
exports.lineEnding = 'lineEnding'

// A line ending, but ending a blank line.
exports.lineEndingBlank = 'lineEndingBlank'

// Generic type for whitespace (tabs, virtual spaces, spaces) at the start of a
// line.
exports.linePrefix = 'linePrefix'

// Generic type for whitespace (tabs, virtual spaces, spaces) at the end of a
// line.
exports.lineSuffix = 'lineSuffix'

// Whole ATX heading:
//
// ```markdown
// #
// ## Alpha
// ### Bravo ###
// ```
//
// Includes `atxHeadingSequence`, `whitespace`, `atxHeadingText`.
exports.atxHeading = 'atxHeading'

// Sequence of number signs in an ATX heading (`###`).
exports.atxHeadingSequence = 'atxHeadingSequence'

// Content in an ATX heading (`alpha`).
// Includes text.
exports.atxHeadingText = 'atxHeadingText'

// Whole autolink (`<https://example.com>` or `<admin@example.com>`)
// Includes `autolinkMarker` and `autolinkProtocol` or `autolinkEmail`.
exports.autolink = 'autolink'

// Email autolink w/o markers (`admin@example.com`)
exports.autolinkEmail = 'autolinkEmail'

// Marker around an `autolinkProtocol` or `autolinkEmail` (`<` or `>`).
exports.autolinkMarker = 'autolinkMarker'

// Protocol autolink w/o markers (`https://example.com`)
exports.autolinkProtocol = 'autolinkProtocol'

// A whole character escape (`\-`).
// Includes `escapeMarker` and `characterEscapeValue`.
exports.characterEscape = 'characterEscape'

// The escaped character (`-`).
exports.characterEscapeValue = 'characterEscapeValue'

// A whole character reference (`&amp;`, `&#8800;`, or `&#x1D306;`).
// Includes `characterReferenceMarker`, an optional
// `characterReferenceMarkerNumeric`, in which case an optional
// `characterReferenceMarkerHexadecimal`, and a `characterReferenceValue`.
exports.characterReference = 'characterReference'

// The start or end marker (`&` or `;`).
exports.characterReferenceMarker = 'characterReferenceMarker'

// Mark reference as numeric (`#`).
exports.characterReferenceMarkerNumeric = 'characterReferenceMarkerNumeric'

// Mark reference as numeric (`x` or `X`).
exports.characterReferenceMarkerHexadecimal =
  'characterReferenceMarkerHexadecimal'

// Value of character reference w/o markers (`amp`, `8800`, or `1D306`).
exports.characterReferenceValue = 'characterReferenceValue'

// Whole fenced code:
//
// ````markdown
// ```js
// alert(1)
// ```
// ````
exports.codeFenced = 'codeFenced'

// A fenced code fence, including whitespace, sequence, info, and meta
// (` ```js `).
exports.codeFencedFence = 'codeFencedFence'

// Sequence of grave accent or tilde characters (` ``` `) in a fence.
exports.codeFencedFenceSequence = 'codeFencedFenceSequence'

// Info word (`js`) in a fence.
// Includes string.
exports.codeFencedFenceInfo = 'codeFencedFenceInfo'

// Meta words (`highlight="1"`) in a fence.
// Includes string.
exports.codeFencedFenceMeta = 'codeFencedFenceMeta'

// A line of code.
exports.codeFlowValue = 'codeFlowValue'

// Whole indented code:
//
// ```markdown
//     alert(1)
// ```
//
// Includes `lineEnding`, `linePrefix`, and `codeFlowValue`.
exports.codeIndented = 'codeIndented'

// A text code (``` `alpha` ```).
// Includes `codeTextSequence`, `codeTextData`, `lineEnding`, and can include
// `codeTextPadding`.
exports.codeText = 'codeText'

exports.codeTextData = 'codeTextData'

// A space or line ending right after or before a tick.
exports.codeTextPadding = 'codeTextPadding'

// A text code fence (` `` `).
exports.codeTextSequence = 'codeTextSequence'

// Whole content:
//
// ```markdown
// [a]: b
// c
// =
// d
// ```
//
// Includes `paragraph` and `definition`.
exports.content = 'content'
// Whole definition:
//
// ```markdown
// [micromark]: https://github.com/micromark/micromark
// ```
//
// Includes `definitionLabel`, `definitionMarker`, `whitespace`,
// `definitionDestination`, and optionally `lineEnding` and `definitionTitle`.
exports.definition = 'definition'

// Destination of a definition (`https://github.com/micromark/micromark` or
// `<https://github.com/micromark/micromark>`).
// Includes `definitionDestinationLiteral` or `definitionDestinationRaw`.
exports.definitionDestination = 'definitionDestination'

// Enclosed destination of a definition
// (`<https://github.com/micromark/micromark>`).
// Includes `definitionDestinationLiteralMarker` and optionally
// `definitionDestinationString`.
exports.definitionDestinationLiteral = 'definitionDestinationLiteral'

// Markers of an enclosed definition destination (`<` or `>`).
exports.definitionDestinationLiteralMarker =
  'definitionDestinationLiteralMarker'

// Unenclosed destination of a definition
// (`https://github.com/micromark/micromark`).
// Includes `definitionDestinationString`.
exports.definitionDestinationRaw = 'definitionDestinationRaw'

// Text in an destination (`https://github.com/micromark/micromark`).
// Includes string.
exports.definitionDestinationString = 'definitionDestinationString'

// Label of a definition (`[micromark]`).
// Includes `definitionLabelMarker` and `definitionLabelString`.
exports.definitionLabel = 'definitionLabel'

// Markers of a definition label (`[` or `]`).
exports.definitionLabelMarker = 'definitionLabelMarker'

// Value of a definition label (`micromark`).
// Includes string.
exports.definitionLabelString = 'definitionLabelString'

// Marker between a label and a destination (`:`).
exports.definitionMarker = 'definitionMarker'

// Title of a definition (`"x"`, `'y'`, or `(z)`).
// Includes `definitionTitleMarker` and optionally `definitionTitleString`.
exports.definitionTitle = 'definitionTitle'

// Marker around a title of a definition (`"`, `'`, `(`, or `)`).
exports.definitionTitleMarker = 'definitionTitleMarker'

// Data without markers in a title (`z`).
// Includes string.
exports.definitionTitleString = 'definitionTitleString'

// Emphasis (`*alpha*`).
// Includes `emphasisSequence` and `emphasisText`.
exports.emphasis = 'emphasis'

// Sequence of emphasis markers (`*` or `_`).
exports.emphasisSequence = 'emphasisSequence'

// Emphasis text (`alpha`).
// Includes text.
exports.emphasisText = 'emphasisText'

// The character escape marker (`\`).
exports.escapeMarker = 'escapeMarker'

// A hard break created with a backslash (`\\n`).
// Includes `escapeMarker` (does not include the line ending)
exports.hardBreakEscape = 'hardBreakEscape'

// A hard break created with trailing spaces (`  \n`).
// Does not include the line ending.
exports.hardBreakTrailing = 'hardBreakTrailing'

// Flow HTML:
//
// ```markdown
// <div
// ```
//
// Inlcudes `lineEnding`, `htmlFlowData`.
exports.htmlFlow = 'htmlFlow'

exports.htmlFlowData = 'htmlFlowData'

// HTML in text (the tag in `a <i> b`).
// Includes `lineEnding`, `htmlTextData`.
exports.htmlText = 'htmlText'

exports.htmlTextData = 'htmlTextData'

// Whole image (`![alpha](bravo)`, `![alpha][bravo]`, `![alpha][]`, or
// `![alpha]`).
// Includes `label` and an optional `resource` or `reference`.
exports.image = 'image'

// Whole link label (`[*alpha*]`).
// Includes `labelLink` or `labelImage`, `labelText`, and `labelEnd`.
exports.label = 'label'

// Text in an label (`*alpha*`).
// Includes text.
exports.labelText = 'labelText'

// Start a link label (`[`).
// Includes a `labelMarker`.
exports.labelLink = 'labelLink'

// Start an image label (`![`).
// Includes `labelImageMarker` and `labelMarker`.
exports.labelImage = 'labelImage'

// Marker of a label (`[` or `]`).
exports.labelMarker = 'labelMarker'

// Marker to start an image (`!`).
exports.labelImageMarker = 'labelImageMarker'

// End a label (`]`).
// Includes `labelMarker`.
exports.labelEnd = 'labelEnd'

// Whole link (`[alpha](bravo)`, `[alpha][bravo]`, `[alpha][]`, or `[alpha]`).
// Includes `label` and an optional `resource` or `reference`.
exports.link = 'link'

// Whole paragraph:
//
// ```markdown
// alpha
// bravo.
// ```
//
// Includes text.
exports.paragraph = 'paragraph'

// A reference (`[alpha]` or `[]`).
// Includes `referenceMarker` and an optional `referenceString`.
exports.reference = 'reference'

// A reference marker (`[` or `]`).
exports.referenceMarker = 'referenceMarker'

// Reference text (`alpha`).
// Includes string.
exports.referenceString = 'referenceString'

// A resource (`(https://example.com "alpha")`).
// Includes `resourceMarker`, an optional `resourceDestination` with an optional
// `whitespace` and `resourceTitle`.
exports.resource = 'resource'

// A resource destination (`https://example.com`).
// Includes `resourceDestinationLiteral` or `resourceDestinationRaw`.
exports.resourceDestination = 'resourceDestination'

// A literal resource destination (`<https://example.com>`).
// Includes `resourceDestinationLiteralMarker` and optionally
// `resourceDestinationString`.
exports.resourceDestinationLiteral = 'resourceDestinationLiteral'

// A resource destination marker (`<` or `>`).
exports.resourceDestinationLiteralMarker = 'resourceDestinationLiteralMarker'

// A raw resource destination (`https://example.com`).
// Includes `resourceDestinationString`.
exports.resourceDestinationRaw = 'resourceDestinationRaw'

// Resource destination text (`https://example.com`).
// Includes string.
exports.resourceDestinationString = 'resourceDestinationString'

// A resource marker (`(` or `)`).
exports.resourceMarker = 'resourceMarker'

// A resource title (`"alpha"`, `'alpha'`, or `(alpha)`).
// Includes `resourceTitleMarker` and optionally `resourceTitleString`.
exports.resourceTitle = 'resourceTitle'

// A resource title marker (`"`, `'`, `(`, or `)`).
exports.resourceTitleMarker = 'resourceTitleMarker'

// Resource destination title (`alpha`).
// Includes string.
exports.resourceTitleString = 'resourceTitleString'

// Whole setext heading:
//
// ```markdown
// alpha
// bravo
// =====
// ```
//
// Includes `setextHeadingText`, `lineEnding`, `linePrefix`, and
// `setextHeadingLine`.
exports.setextHeading = 'setextHeading'

// Content in a setext heading (`alpha\nbravo`).
// Includes text.
exports.setextHeadingText = 'setextHeadingText'

// Underline in a setext heading, including whitespace suffix (`==`).
// Includes `setextHeadingLineSequence`.
exports.setextHeadingLine = 'setextHeadingLine'

// Sequence of equals or dash characters in underline in a setext heading (`-`).
exports.setextHeadingLineSequence = 'setextHeadingLineSequence'

// Strong (`**alpha**`).
// Includes `strongSequence` and `strongText`.
exports.strong = 'strong'

// Sequence of strong markers (`**` or `__`).
exports.strongSequence = 'strongSequence'

// Strong text (`alpha`).
// Includes text.
exports.strongText = 'strongText'

// Whole thematic break:
//
// ```markdown
// * * *
// ```
//
// Includes `thematicBreakSequence` and `whitespace`.
exports.thematicBreak = 'thematicBreak'

// A sequence of one or more thematic break markers (`***`).
exports.thematicBreakSequence = 'thematicBreakSequence'

// Whole block quote:
//
// ```markdown
// > a
// >
// > b
// ```
//
// Includes `blockQuotePrefix` and flow.
exports.blockQuote = 'blockQuote'
// The `>` or `> ` of a block quote.
exports.blockQuotePrefix = 'blockQuotePrefix'
// The `>` of a block quote prefix.
exports.blockQuoteMarker = 'blockQuoteMarker'
// The optional ` ` of a block quote prefix.
exports.blockQuotePrefixWhitespace = 'blockQuotePrefixWhitespace'

// Whole unordered list:
//
// ```markdown
// - a
//   b
// ```
//
// Includes `listItemPrefix`, flow, and optionally  `listItemIndent` on further
// lines.
exports.listOrdered = 'listOrdered'

// Whole ordered list:
//
// ```markdown
// 1. a
//    b
// ```
//
// Includes `listItemPrefix`, flow, and optionally  `listItemIndent` on further
// lines.
exports.listUnordered = 'listUnordered'

// The indent of further list item lines.
exports.listItemIndent = 'listItemIndent'

// A marker, as in, `*`, `+`, `-`, `.`, or `)`.
exports.listItemMarker = 'listItemMarker'

// The thing that starts a list item, such as `1. `.
// Includes `listItemValue` if ordered, `listItemMarker`, and
// `listItemPrefixWhitespace` (unless followed by a line ending).
exports.listItemPrefix = 'listItemPrefix'

// The whitespace after a marker.
exports.listItemPrefixWhitespace = 'listItemPrefixWhitespace'

// The numerical value of an ordered item.
exports.listItemValue = 'listItemValue'

// Internal types used for subtokenizers, compiled away
exports.chunkContent = 'chunkContent'
exports.chunkFlow = 'chunkFlow'
exports.chunkText = 'chunkText'
exports.chunkString = 'chunkString'
