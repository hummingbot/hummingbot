Prism.languages.scheme = {
	// this supports "normal" single-line comments:
	//   ; comment
	// and (potentially nested) multiline comments:
	//   #| comment #| nested |# still comment |#
	// (only 1 level of nesting is supported)
	'comment': /;.*|#;\s*\((?:[^()]|\([^()]*\))*\)|#\|(?:[^#|]|#(?!\|)|\|(?!#)|#\|(?:[^#|]|#(?!\|)|\|(?!#))*\|#)*\|#/,
	'string': {
		pattern: /"(?:[^"\\]|\\.)*"/,
		greedy: true
	},
	'symbol': {
		pattern: /'[^()#'\s]+/,
		greedy: true
	},
	'character': {
		pattern: /#\\(?:[ux][a-fA-F\d]+\b|[-a-zA-Z]+\b|\S)/,
		greedy: true,
		alias: 'string'
	},
	'lambda-parameter': [
		// https://www.cs.cmu.edu/Groups/AI/html/r4rs/r4rs_6.html#SEC30
		{
			pattern: /(\(lambda\s+)(?:[^|()'\s]+|\|(?:[^\\|]|\\.)*\|)/,
			lookbehind: true
		},
		{
			pattern: /(\(lambda\s+\()[^()']+/,
			lookbehind: true
		}
	],
	'keyword': {
		pattern: /(\()(?:begin|case(?:-lambda)?|cond(?:-expand)?|define(?:-library|-macro|-record-type|-syntax|-values)?|defmacro|delay(?:-force)?|do|else|export|except|guard|if|import|include(?:-ci|-library-declarations)?|lambda|let(?:rec)?(?:-syntax|-values|\*)?|let\*-values|only|parameterize|prefix|(?:quasi-?)?quote|rename|set!|syntax-(?:case|rules)|unless|unquote(?:-splicing)?|when)(?=[()\s]|$)/,
		lookbehind: true
	},
	'builtin': {
		// all functions of the base library of R7RS plus some of built-ins of R5Rs
		pattern: /(\()(?:abs|and|append|apply|assoc|ass[qv]|binary-port\?|boolean=?\?|bytevector(?:-append|-copy|-copy!|-length|-u8-ref|-u8-set!|\?)?|caar|cadr|call-with-(?:current-continuation|port|values)|call\/cc|car|cdar|cddr|cdr|ceiling|char(?:->integer|-ready\?|\?|<\?|<=\?|=\?|>\?|>=\?)|close-(?:input-port|output-port|port)|complex\?|cons|current-(?:error|input|output)-port|denominator|dynamic-wind|eof-object\??|eq\?|equal\?|eqv\?|error|error-object(?:-irritants|-message|\?)|eval|even\?|exact(?:-integer-sqrt|-integer\?|\?)?|expt|features|file-error\?|floor(?:-quotient|-remainder|\/)?|flush-output-port|for-each|gcd|get-output-(?:bytevector|string)|inexact\??|input-port(?:-open\?|\?)|integer(?:->char|\?)|lcm|length|list(?:->string|->vector|-copy|-ref|-set!|-tail|\?)?|make-(?:bytevector|list|parameter|string|vector)|map|max|member|memq|memv|min|modulo|negative\?|newline|not|null\?|number(?:->string|\?)|numerator|odd\?|open-(?:input|output)-(?:bytevector|string)|or|output-port(?:-open\?|\?)|pair\?|peek-char|peek-u8|port\?|positive\?|procedure\?|quotient|raise|raise-continuable|rational\?|rationalize|read-(?:bytevector|bytevector!|char|error\?|line|string|u8)|real\?|remainder|reverse|round|set-c[ad]r!|square|string(?:->list|->number|->symbol|->utf8|->vector|-append|-copy|-copy!|-fill!|-for-each|-length|-map|-ref|-set!|\?|<\?|<=\?|=\?|>\?|>=\?)?|substring|symbol(?:->string|\?|=\?)|syntax-error|textual-port\?|truncate(?:-quotient|-remainder|\/)?|u8-ready\?|utf8->string|values|vector(?:->list|->string|-append|-copy|-copy!|-fill!|-for-each|-length|-map|-ref|-set!|\?)?|with-exception-handler|write-(?:bytevector|char|string|u8)|zero\?)(?=[()\s]|$)/,
		lookbehind: true
	},
	'operator': {
		pattern: /(\()(?:[-+*%/]|[<>]=?|=>?)(?=[()\s]|$)/,
		lookbehind: true
	},
	'number': {
		// This pattern (apart from the lookarounds) works like this:
		//
		// Decimal numbers
		// <dec real>       := \d*\.?\d+(?:[eE][+-]?\d+)?|\d+\/\d+
		// <dec complex>    := <dec real>(?:[+-]<dec real>i)?|<dec real>i
		// <dec prefix>     := (?:#d(?:#[ei])?|#[ei](?:#d)?)?
		// <dec number>     := <dec prefix>[+-]?<complex>
		//
		// Binary, octal, and hexadecimal numbers
		// <b.o.x. real>    := [\da-fA-F]+(?:\/[\da-fA-F]+)?
		// <b.o.x. complex> := <b.o.x. real>(?:[+-]<b.o.x. real>i)?|<b.o.x. real>i
		// <b.o.x. prefix>  := #[box](?:#[ei])?|#[ei](?:#[box])?
		// <b.o.x. number>  := <b.o.x. prefix>[+-]?<b.o.x. complex>
		//
		// <number>         := <dec number>|<b.o.x. number>
		pattern: /(^|[\s()])(?:(?:#d(?:#[ei])?|#[ei](?:#d)?)?[+-]?(?:(?:\d*\.?\d+(?:[eE][+-]?\d+)?|\d+\/\d+)(?:[+-](?:\d*\.?\d+(?:[eE][+-]?\d+)?|\d+\/\d+)i)?|(?:\d*\.?\d+(?:[eE][+-]?\d+)?|\d+\/\d+)i)|(?:#[box](?:#[ei])?|#[ei](?:#[box])?)[+-]?(?:[\da-fA-F]+(?:\/[\da-fA-F]+)?(?:[+-][\da-fA-F]+(?:\/[\da-fA-F]+)?i)?|[\da-fA-F]+(?:\/[\da-fA-F]+)?i))(?=[()\s]|$)/,
		lookbehind: true
	},
	'boolean': {
		pattern: /(^|[\s()])#(?:[ft]|false|true)(?=[()\s]|$)/,
		lookbehind: true
	},
	'function': {
		pattern: /(\()(?:[^|()'\s]+|\|(?:[^\\|]|\\.)*\|)(?=[()\s]|$)/,
		lookbehind: true
	},
	'identifier': {
		pattern: /(^|[\s()])\|(?:[^\\|]|\\.)*\|(?=[()\s]|$)/,
		lookbehind: true,
		greedy: true
	},
	'punctuation': /[()']/
};
