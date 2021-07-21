export default function locate(source, index) {
	const lines = source.split('\n');
	const len = lines.length;

	let lineStart = 0;
	let i;

	for (i = 0; i < len; i += 1) {
		const line = lines[i];
		const lineEnd = lineStart + line.length + 1; // +1 for newline

		if (lineEnd > index) {
			return { line: i + 1, column: index - lineStart, char: i };
		}

		lineStart = lineEnd;
	}

	throw new Error('Could not determine location of character');
}
