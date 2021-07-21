Prism.languages.racket = Prism.languages.extend('scheme', {
	'lambda-parameter': {
		// the racket lambda syntax is a lot more complex, so we won't even attempt to capture it.
		// this will just prevent false positives of the `function` pattern
		pattern: /(\(lambda\s+\()[^()'\s]+/,
		lookbehind: true
	}
});

// Add brackets to racket
// The basic idea here is to go through all pattens of Scheme and replace all occurrences of "(" with the union of "("
// and "["; Similar for ")". This is a bit tricky because "(" can be escaped or inside a character set. Both cases
// have to be handled differently and, of course, we don't want to destroy groups, so we can only replace literal "("
// and ")".
// To do this, we use a regular expression which will parse any JS regular expression. It works because regexes are
// matches from left to right and already matched text cannot be matched again. We use this to first capture all
// escaped characters (not really, we don't get escape sequences but we don't need them). Because we already captured
// all escaped characters, we know that any "[" character is the start of a character set, so we match that character
// set whole.
// With the regex parsed, we only have to replace all escaped "(" (they cannot be unescaped outside of character sets)
// with /[([]/ and replace all "(" inside character sets.
// Note: This method does not work for "(" that are escaped like this /\x28/ or this /\u0028/.
Prism.languages.DFS(Prism.languages.racket, function (key, value) {
	if (Prism.util.type(value) === 'RegExp') {
		var source = value.source.replace(/\\(.)|\[\^?((?:\\.|[^\\\]])*)\]/g, function (m, g1, g2) {
			if (g1) {
				if (g1 === '(') {
					// replace all '(' characters outside character sets
					return '[([]';
				}
				if (g1 === ')') {
					// replace all ')' characters outside character sets
					return '[)\\]]';
				}
			}
			if (g2) {
				var prefix = m[1] === '^' ? '[^' : '[';
				return prefix + g2.replace(/\\(.)|[()]/g, function (m, g1) {
					if (m === '(' || g1 === '(') {
						// replace all '(' characters inside character sets
						return '([';
					}
					if (m === ')' || g1 === ')') {
						// replace all ')' characters inside character sets
						return ')\\]';
					}
					return m;
				}) + ']';
			}
			return m;
		});

		this[key] = RegExp(source, value.flags);
	}
});

Prism.languages.insertBefore('racket', 'string', {
	'lang': {
		pattern: /^#lang.+/m,
		greedy: true,
		alias: 'keyword'
	}
});

Prism.languages.rkt = Prism.languages.racket;
