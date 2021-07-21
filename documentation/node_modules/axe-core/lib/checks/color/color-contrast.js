const { dom, color, text } = axe.commons;

if (!dom.isVisible(node, false)) {
	return true;
}

const visibleText = text.visibleVirtual(virtualNode, false, true);
const ignoreUnicode = !!(options || {}).ignoreUnicode;
const textContainsOnlyUnicode =
	text.hasUnicode(visibleText, {
		nonBmp: true
	}) &&
	text.sanitize(
		text.removeUnicode(visibleText, {
			nonBmp: true
		})
	) === '';

if (textContainsOnlyUnicode && ignoreUnicode) {
	this.data({ messageKey: 'nonBmp' });
	return undefined;
}

const noScroll = !!(options || {}).noScroll;
const bgNodes = [];
const bgColor = color.getBackgroundColor(node, bgNodes, noScroll);
const fgColor = color.getForegroundColor(node, noScroll, bgColor);

const nodeStyle = window.getComputedStyle(node);
const fontSize = parseFloat(nodeStyle.getPropertyValue('font-size'));
const fontWeight = nodeStyle.getPropertyValue('font-weight');
const bold = parseFloat(fontWeight) >= 700 || fontWeight === 'bold';

const cr = color.hasValidContrastRatio(bgColor, fgColor, fontSize, bold);

// truncate ratio to three digits while rounding down
// 4.499 = 4.49, 4.019 = 4.01
const truncatedResult = Math.floor(cr.contrastRatio * 100) / 100;

// if fgColor or bgColor are missing, get more information.
let missing;
if (bgColor === null) {
	missing = color.incompleteData.get('bgColor');
}

const equalRatio = truncatedResult === 1;
const shortTextContent = visibleText.length === 1;
const ignoreLength = !!(options || {}).ignoreLength;
if (equalRatio) {
	missing = color.incompleteData.set('bgColor', 'equalRatio');
} else if (shortTextContent && !ignoreLength) {
	// Check that the text content is a single character long
	missing = 'shortTextContent';
}

// need both independently in case both are missing
const data = {
	fgColor: fgColor ? fgColor.toHexString() : undefined,
	bgColor: bgColor ? bgColor.toHexString() : undefined,
	contrastRatio: cr ? truncatedResult : undefined,
	fontSize: `${((fontSize * 72) / 96).toFixed(1)}pt (${fontSize}px)`,
	fontWeight: bold ? 'bold' : 'normal',
	messageKey: missing,
	expectedContrastRatio: cr.expectedContrastRatio + ':1'
};

this.data(data);

// We don't know, so we'll put it into Can't Tell
if (
	fgColor === null ||
	bgColor === null ||
	equalRatio ||
	(shortTextContent && !ignoreLength && !cr.isValid)
) {
	missing = null;
	color.incompleteData.clear();
	this.relatedNodes(bgNodes);
	return undefined;
}

if (!cr.isValid) {
	this.relatedNodes(bgNodes);
}

return cr.isValid;
