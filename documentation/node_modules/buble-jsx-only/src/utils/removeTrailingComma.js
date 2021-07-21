export default function removeTrailingComma(code, c) {
	while (code.original[c] !== ')') {
		if (code.original[c] === ',') {
			code.remove(c, c + 1);
			return;
		}

		if (code.original[c] === '/') {
			if (code.original[c + 1] === '/') {
				c = code.original.indexOf('\n', c);
			} else {
				c = code.original.indexOf('*/', c) + 1;
			}
		}
		c += 1;
	}
}
