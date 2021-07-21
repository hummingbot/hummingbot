function pad(num, len) {
	const result = String(num);
	return result + repeat(' ', len - result.length);
}

function repeat(str, times) {
	let result = '';
	while (times--) result += str;
	return result;
}

export default function getSnippet(source, loc, length = 1) {
	const first = Math.max(loc.line - 5, 0);
	const last = loc.line;

	const numDigits = String(last).length;

	const lines = source.split('\n').slice(first, last);

	const lastLine = lines[lines.length - 1];
	const offset = lastLine.slice(0, loc.column).replace(/\t/g, '  ').length;

	let snippet = lines
		.map((line, i) => `${pad(i + first + 1, numDigits)} : ${line.replace(/\t/g, '  ')}`)
		.join('\n');

	snippet += '\n' + repeat(' ', numDigits + 3 + offset) + repeat('^', length);

	return snippet;
}
