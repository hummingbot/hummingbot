/*
Original Code by Bas Groothedde
!!MANY THANKS!! I never would have made this, regex and me will never be best friends ;)
==> https://codepen.io/ImagineProgramming/details/JYydBy/
slightly changed to pass all tests
*/


// PureBasic support, steal stuff from ansi-c
Prism.languages.purebasic = Prism.languages.extend('clike', {
	'comment': /;.*/,
	'keyword': /\b(?:declarecdll|declaredll|compilerselect|compilercase|compilerdefault|compilerendselect|compilererror|enableexplicit|disableexplicit|not|and|or|xor|calldebugger|debuglevel|enabledebugger|disabledebugger|restore|read|includepath|includebinary|threaded|runtime|with|endwith|structureunion|endstructureunion|align|newlist|newmap|interface|endinterface|extends|enumeration|endenumeration|swap|foreach|continue|fakereturn|goto|gosub|return|break|module|endmodule|declaremodule|enddeclaremodule|declare|declarec|prototype|prototypec|enableasm|disableasm|dim|redim|data|datasection|enddatasection|to|procedurereturn|debug|default|case|select|endselect|as|import|endimport|importc|compilerif|compilerelse|compilerendif|compilerelseif|end|structure|endstructure|while|wend|for|next|step|if|else|elseif|endif|repeat|until|procedure|proceduredll|procedurec|procedurecdll|endprocedure|protected|shared|static|global|define|includefile|xincludefile|macro|endmacro)\b/i,
	'function': /\b\w+(?:\.\w+)?\s*(?=\()/,
	'number': /(?:\$[\da-f]+|\b-?\d*\.?\d+(?:e[+-]?\d+)?)\b/i,
	'operator': /(?:@\*?|\?|\*)\w+|-[>-]?|\+\+?|!=?|<<?=?|>>?=?|==?|&&?|\|?\||[~^%?*/@]/
});

Prism.languages.insertBefore('purebasic', 'keyword', {
	'tag': /#\w+/,
	'asm': {
		pattern: /(^\s*)!.*/m,
		lookbehind: true,
		alias: 'tag',
		inside: {
			'comment': /;.*/,
			'string': {
				pattern: /(["'`])(?:\\.|(?!\1)[^\\\r\n])*\1/,
				greedy: true
			},
			// Anonymous label references, i.e.: jmp @b
			'label-reference-anonymous': {
				pattern: /(\s*!\s*j[a-z]+\s+)@[fb]/i,
				lookbehind: true,
				alias: 'fasm-label'
			},
			// Named label reference, i.e.: jne label1
			'label-reference-addressed': {
				pattern: /(\s*!\s*j[a-z]+\s+)[A-Z._?$@][\w.?$@~#]*/i,
				lookbehind: true,
				alias: 'fasm-label'
			},
			'function': {
				pattern: /^(\s*!\s*)[\da-z]+(?=\s|$)/im,
				lookbehind: true
			},
			'function-inline': {
				pattern: /(\s*:\s*)[\da-z]+(?=\s)/i,
				lookbehind: true,
				alias: 'function'
			},
			'label': {
				pattern: /^(\s*!\s*)[A-Za-z._?$@][\w.?$@~#]*(?=:)/m,
				lookbehind: true,
				alias: 'fasm-label'
			},
			'keyword': [
				/(?:extern|global)[^;\r\n]*/i,
				/(?:CPU|FLOAT|DEFAULT).*/
			],
			'register': /\b(?:st\d|[xyz]mm\d\d?|[cdt]r\d|r\d\d?[bwd]?|[er]?[abcd]x|[abcd][hl]|[er]?(?:bp|sp|si|di)|[cdefgs]s|mm\d+)\b/i,
			'number': /(?:\b|-|(?=\$))(?:0[hx][\da-f]*\.?[\da-f]+(?:p[+-]?\d+)?|\d[\da-f]+[hx]|\$\d[\da-f]*|0[oq][0-7]+|[0-7]+[oq]|0[by][01]+|[01]+[by]|0[dt]\d+|\d*\.?\d+(?:\.?e[+-]?\d+)?[dt]?)\b/i,
			'operator': /[\[\]*+\-/%<>=&|$!,.:]/
		}
	}
});

delete Prism.languages.purebasic['class-name'];
delete Prism.languages.purebasic['boolean'];

Prism.languages.pbfasm = Prism.languages['purebasic'];
