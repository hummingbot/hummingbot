Prism.languages.birb = Prism.languages.extend('clike', {
	'class-name': [
		/\b[A-Z](?:[\d_]*[a-zA-Z]\w*)?\b/,

		// matches variable and function return types (parameters as well).
		/\b[A-Z]\w*(?=\s+\w+\s*[;,=()])/
	],
	'string': {
		pattern: /r?("|')(?:\\.|(?!\1)[^\\])*\1/,
		greedy: true
	},
	'keyword': /\b(?:assert|break|case|class|const|default|else|enum|final|follows|for|grab|if|nest|next|new|noSeeb|return|static|switch|throw|var|void|while)\b/,
	'variable': /\b[a-z_]\w*\b/,
	'operator': /\+\+|--|&&|\|\||<<=?|>>=?|~(?:\/=?)?|[+\-*\/%&^|=!<>]=?|\?|:/,
});

Prism.languages.insertBefore('birb','function',{
	'metadata': {
		pattern: /<\w+>/,
		greedy: true,
		alias: 'symbol'
	}
});