// https://mc-stan.org/docs/2_24/reference-manual/bnf-grammars.html

Prism.languages.stan = {
	'comment': /\/\/.*|\/\*[\s\S]*?\*\/|#(?!include).*/,
	'string': {
		// String literals can contain spaces and any printable ASCII characters except for " and \
		// https://mc-stan.org/docs/2_24/reference-manual/print-statements-section.html#string-literals
		pattern: /"[\x20\x21\x23-\x5B\x5D-\x7E]*"/,
		greedy: true
	},
	'directive': {
		pattern: /^([ \t]*)#include\b.*/m,
		lookbehind: true,
		alias: 'property'
	},

	'function-arg': {
		pattern: /(\b(?:algebra_solver|integrate_1d|integrate_ode|integrate_ode_bdf|integrate_ode_rk45|map_rect)\s*\(\s*)[a-zA-Z]\w*/,
		lookbehind: true,
		alias: 'function'
	},
	'constraint': {
		pattern: /(\b(?:int|matrix|real|row_vector|vector)\s*)<[^<>]*>/,
		lookbehind: true,
		inside: {
			'expression': {
				pattern: /(=\s*)(?:(?!\s*(?:>$|,\s*\w+\s*=))[\s\S])+/,
				lookbehind: true,
				inside: null // see below
			},
			'property': /\b[a-z]\w*(?=\s*=)/i,
			'operator': /=/,
			'punctuation': /^<|>$|[,]/
		}
	},
	'keyword': [
		/\b(?:break|cholesky_factor_corr|cholesky_factor_cov|continue|corr_matrix|cov_matrix|data|else|for|functions|generated|if|in|increment_log_prob|int|matrix|model|ordered|parameters|positive_ordered|print|quantities|real|reject|return|row_vector|simplex|target|transformed|unit_vector|vector|void|while)\b/,
		// these are functions that are known to take another function as their first argument.
		/\b(?:algebra_solver|integrate_1d|integrate_ode|integrate_ode_bdf|integrate_ode_rk45|map_rect)\b/
	],
	'function': /\b[a-z]\w*(?=\s*\()/i,
	'number': /(?:\b\d+(?:\.\d*)?|\B\.\d+)(?:E[+-]?\d+)?\b/i,
	'boolean': /\b(?:false|true)\b/,

	'operator': /<-|\.[*/]=?|\|\|?|&&|[!=<>+\-*/]=?|['^%~?:]/,
	'punctuation': /[()\[\]{},;]/
};

Prism.languages.stan.constraint.inside.expression.inside = Prism.languages.stan;
