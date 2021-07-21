/**
 * Original by Scott Helme.
 *
 * Reference: https://scotthelme.co.uk/csp-cheat-sheet/
 *
 * Supports the following:
 *  - CSP Level 1
 *  - CSP Level 2
 *  - CSP Level 3
 */

Prism.languages.csp = {
	'directive':  {
		pattern: /\b(?:base-uri|block-all-mixed-content|(?:child|connect|default|font|frame|img|manifest|media|object|script|style|worker)-src|disown-opener|form-action|frame-ancestors|plugin-types|referrer|reflected-xss|report-to|report-uri|require-sri-for|sandbox|upgrade-insecure-requests)\b/i,
		alias: 'keyword'
	},
	'safe': {
		pattern: /'(?:self|none|strict-dynamic|(?:nonce-|sha(?:256|384|512)-)[a-zA-Z\d+=/]+)'/,
		alias: 'selector'
	},
	'unsafe': {
		pattern: /(?:'unsafe-inline'|'unsafe-eval'|'unsafe-hashed-attributes'|\*)/,
		alias: 'function'
	}
};