// TODO this function is slightly flawed – it works on the original string,
// not its current edited state.
// That's not a problem for the way that it's currently used, but it could
// be in future...
export default function deindent(node, code) {
	const start = node.start;
	const end = node.end;

	const indentStr = code.getIndentString();
	const indentStrLen = indentStr.length;
	const indentStart = start - indentStrLen;

	if (
		!node.program.indentExclusions[indentStart] &&
		code.original.slice(indentStart, start) === indentStr
	) {
		code.remove(indentStart, start);
	}

	const pattern = new RegExp(indentStr + '\\S', 'g');
	const slice = code.original.slice(start, end);
	let match;

	while ((match = pattern.exec(slice))) {
		const removeStart = start + match.index;
		if (!node.program.indentExclusions[removeStart]) {
			code.remove(removeStart, removeStart + indentStrLen);
		}
	}
}
