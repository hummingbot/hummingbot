const { text } = axe.commons;
const { pixelThreshold, occuranceThreshold } = options || {};

const accText = text.accessibleText(node).toLowerCase();
if (text.isHumanInterpretable(accText) < 1) {
	return undefined;
}

const textVNodes = text.visibleTextNodes(virtualNode);
const nonLigatureText = textVNodes
	.filter(
		textVNode =>
			!text.isIconLigature(textVNode, pixelThreshold, occuranceThreshold)
	)
	.map(textVNode => textVNode.actualNode.nodeValue)
	.join('');
const visibleText = text.sanitize(nonLigatureText).toLowerCase();
if (!visibleText) {
	return true;
}
if (text.isHumanInterpretable(visibleText) < 1) {
	if (isStringContained(visibleText, accText)) {
		return true;
	}
	return undefined;
}

return isStringContained(visibleText, accText);

/**
 * Check if a given text exists in another
 *
 * @param {String} compare given text to check
 * @param {String} compareWith text against which to be compared
 * @returns {Boolean}
 */
function isStringContained(compare, compareWith) {
	const curatedCompareWith = curateString(compareWith);
	const curatedCompare = curateString(compare);
	if (!curatedCompareWith || !curatedCompare) {
		return false;
	}
	return curatedCompareWith.includes(curatedCompare);
}

/**
 * Curate given text, by removing emoji's, punctuations, unicode and trim whitespace.
 *
 * @param {String} str given text to curate
 * @returns {String}
 */
function curateString(str) {
	const noUnicodeStr = text.removeUnicode(str, {
		emoji: true,
		nonBmp: true,
		punctuations: true
	});
	return text.sanitize(noUnicodeStr);
}
