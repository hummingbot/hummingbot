let siblings = Array.from(node.parentNode.children);
let currentIndex = siblings.indexOf(node);

options = options || {};
let margins = options.margins || [];

let nextSibling = siblings
	.slice(currentIndex + 1)
	.find(elm => elm.nodeName.toUpperCase() === 'P');

let prevSibling = siblings
	.slice(0, currentIndex)
	.reverse()
	.find(elm => elm.nodeName.toUpperCase() === 'P');

function getTextContainer(elm) {
	let nextNode = elm;
	let outerText = elm.textContent.trim();
	let innerText = outerText;

	while (innerText === outerText && nextNode !== undefined) {
		let i = -1;
		elm = nextNode;
		if (elm.children.length === 0) {
			return elm;
		}

		do {
			// find the first non-empty child
			i++;
			innerText = elm.children[i].textContent.trim();
		} while (innerText === '' && i + 1 < elm.children.length);
		nextNode = elm.children[i];
	}

	return elm;
}

function normalizeFontWeight(weight) {
	/* eslint indent: 0*/
	switch (weight) {
		case 'lighter':
			return 100;
		case 'normal':
			return 400;
		case 'bold':
			return 700;
		case 'bolder':
			return 900;
	}
	weight = parseInt(weight);
	return !isNaN(weight) ? weight : 400;
}

function getStyleValues(node) {
	let style = window.getComputedStyle(getTextContainer(node));
	return {
		fontWeight: normalizeFontWeight(style.getPropertyValue('font-weight')),
		fontSize: parseInt(style.getPropertyValue('font-size')),
		isItalic: style.getPropertyValue('font-style') === 'italic'
	};
}

function isHeaderStyle(styleA, styleB, margins) {
	return margins.reduce((out, margin) => {
		return (
			out ||
			((!margin.size || styleA.fontSize / margin.size > styleB.fontSize) &&
				(!margin.weight ||
					styleA.fontWeight - margin.weight > styleB.fontWeight) &&
				(!margin.italic || (styleA.isItalic && !styleB.isItalic)))
		);
	}, false);
}

const currStyle = getStyleValues(node);
const nextStyle = nextSibling ? getStyleValues(nextSibling) : null;
const prevStyle = prevSibling ? getStyleValues(prevSibling) : null;

if (!nextStyle || !isHeaderStyle(currStyle, nextStyle, margins)) {
	return true;
}

let blockquote = axe.commons.dom.findUpVirtual(virtualNode, 'blockquote');
if (blockquote && blockquote.nodeName.toUpperCase() === 'BLOCKQUOTE') {
	return undefined;
}

if (prevStyle && !isHeaderStyle(currStyle, prevStyle, margins)) {
	return undefined;
}

return false;
