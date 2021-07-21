/* global text, aria */
/**
 * Get the accessible text for an element that can get its name from content
 *
 * @param {VirtualNode} element
 * @param {Object} context
 * @property {Bool} strict Should the name computation strictly follow AccName 1.1
 * @return {String} Accessible text
 */
text.subtreeText = function subtreeText(virtualNode, context = {}) {
	const { alreadyProcessed } = text.accessibleTextVirtual;
	context.startNode = context.startNode || virtualNode;
	const { strict } = context;
	if (
		alreadyProcessed(virtualNode, context) ||
		!aria.namedFromContents(virtualNode, { strict })
	) {
		return '';
	}

	return aria.getOwnedVirtual(virtualNode).reduce((contentText, child) => {
		return appendAccessibleText(contentText, child, context);
	}, '');
};

// TODO: Could do with an "HTML" lookup table, similar to ARIA,
//  where this sort of stuff can live.
const phrasingElements = [
	'A',
	'EM',
	'STRONG',
	'SMALL',
	'MARK',
	'ABBR',
	'DFN',
	'I',
	'B',
	'S',
	'U',
	'CODE',
	'VAR',
	'SAMP',
	'KBD',
	'SUP',
	'SUB',
	'Q',
	'CITE',
	'SPAN',
	'BDO',
	'BDI',
	'WBR',
	'INS',
	'DEL',
	'MAP',
	'AREA',
	'NOSCRIPT',
	'RUBY',
	'BUTTON',
	'LABEL',
	'OUTPUT',
	'DATALIST',
	'KEYGEN',
	'PROGRESS',
	'COMMAND',
	'CANVAS',
	'TIME',
	'METER',
	'#TEXT'
];

function appendAccessibleText(contentText, virtualNode, context) {
	const nodeName = virtualNode.actualNode.nodeName.toUpperCase();
	let contentTextAdd = text.accessibleTextVirtual(virtualNode, context);
	if (!contentTextAdd) {
		return contentText;
	}

	if (!phrasingElements.includes(nodeName)) {
		// Append space, if necessary
		if (contentTextAdd[0] !== ' ') {
			contentTextAdd += ' ';
		}
		// Prepend space, if necessary
		if (contentText && contentText[contentText.length - 1] !== ' ') {
			contentTextAdd = ' ' + contentTextAdd;
		}
	}
	return contentText + contentTextAdd;
}
