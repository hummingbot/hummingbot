// This module is compiled away!
//
// Parsing markdown comes with a couple of constants, such as minimum or maximum
// sizes of certain sequences.
// Additionally, there are a couple symbols used inside micromark.
// These are all defined here, but compiled away by scripts.
exports.asciiAlphaCaseDifference = 32 // The shift between lower- and uppercase is `0x20`.
exports.attentionSideBefore = 1 // Symbol to mark an attention sequence as before content: `*a`
exports.attentionSideAfter = 2 // Symbol to mark an attention sequence as after content: `a*`
exports.atxHeadingOpeningFenceSizeMax = 6 // 6 number signs is fine, 7 isn’t.
exports.autolinkDomainSizeMax = 63 // 63 characters is fine, 64 is too many.
exports.autolinkSchemeSizeMax = 32 // 32 characters is fine, 33 is too many.
exports.cdataOpeningString = 'CDATA[' // And preceded by `<![`.
exports.characterGroupWhitespace = 1 // Symbol used to indicate a character is whitespace
exports.characterGroupPunctuation = 2 // Symbol used to indicate a character is whitespace
exports.characterReferenceDecimalSizeMax = 7 // `&#9999999;`.
exports.characterReferenceHexadecimalSizeMax = 6 // `&#xff9999;`.
exports.characterReferenceNamedSizeMax = 31 // `&CounterClockwiseContourIntegral;`.
exports.codeFencedSequenceSizeMin = 3 // At least 3 ticks or tildes are needed.
exports.contentTypeFlow = 'flow'
exports.contentTypeContent = 'content'
exports.contentTypeString = 'string'
exports.contentTypeText = 'text'
exports.hardBreakPrefixSizeMin = 2 // At least 2 trailing spaces are needed.
exports.htmlRaw = 1 // Symbol for `<script>`
exports.htmlComment = 2 // Symbol for `<!---->`
exports.htmlInstruction = 3 // Symbol for `<?php?>`
exports.htmlDeclaration = 4 // Symbol for `<!doctype>`
exports.htmlCdata = 5 // Symbol for `<![CDATA[]]>`
exports.htmlBasic = 6 // Symbol for `<div`
exports.htmlComplete = 7 // Symbol for `<x>`
exports.htmlRawSizeMax = 6 // Length of `script`.
exports.linkResourceDestinationBalanceMax = 3 // See: <https://spec.commonmark.org/0.29/#link-destination>
exports.linkReferenceSizeMax = 999 // See: <https://spec.commonmark.org/0.29/#link-label>
exports.listItemValueSizeMax = 10 // See: <https://spec.commonmark.org/0.29/#ordered-list-marker>
exports.numericBaseDecimal = 10
exports.numericBaseHexadecimal = 0x10
exports.tabSize = 4 // Tabs have a hard-coded size of 4, per CommonMark.
exports.thematicBreakMarkerCountMin = 3 // At least 3 asterisks, dashes, or underscores are needed.
exports.v8MaxSafeChunkSize = 10000 // V8 (and potentially others) have problems injecting giant arrays into other arrays, hence we operate in chunks.
