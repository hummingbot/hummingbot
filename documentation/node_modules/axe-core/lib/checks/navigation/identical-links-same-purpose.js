/**
 * Note: `identical-links-same-purpose-after` fn, helps reconcile the results
 */
const { dom, text } = axe.commons;

const accText = text.accessibleTextVirtual(virtualNode);
const name = text
	.sanitize(
		text.removeUnicode(accText, {
			emoji: true,
			nonBmp: true,
			punctuations: true
		})
	)
	.toLowerCase();

if (!name) {
	return undefined;
}

/**
 * Set `data` and `relatedNodes` for use in `after` fn
 */
const afterData = {
	name,
	urlProps: dom.urlPropsFromAttribute(node, 'href')
};
this.data(afterData);
this.relatedNodes([node]);

return true;
