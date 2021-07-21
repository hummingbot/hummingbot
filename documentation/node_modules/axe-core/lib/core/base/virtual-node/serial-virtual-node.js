// eslint-disable-next-line no-unused-vars
class SerialVirtualNode extends axe.AbstractVirtualNode {
	/**
	 * Convert a serialised node into a VirtualNode object
	 * @param {Object} node Serialised node
	 */
	constructor(serialNode) {
		super();
		this._props = normaliseProps(serialNode);
		this._attrs = normaliseAttrs(serialNode);
	}

	// Accessof for DOM node properties
	get props() {
		return this._props;
	}

	/**
	 * Get the value of the given attribute name.
	 * @param {String} attrName The name of the attribute.
	 * @return {String|null} The value of the attribute or null if the attribute does not exist
	 */
	attr(attrName) {
		return this._attrs[attrName] || null;
	}

	/**
	 * Determine if the element has the given attribute.
	 * @param {String} attrName The name of the attribute
	 * @return {Boolean} True if the element has the attribute, false otherwise.
	 */
	hasAttr(attrName) {
		return this._attrs[attrName] !== undefined;
	}
}

/**
 * Convert between serialised props and DOM-like properties
 * @param {Object} serialNode
 * @return {Object} normalProperties
 */
function normaliseProps(serialNode) {
	let { nodeName, nodeType = 1 } = serialNode;
	axe.utils.assert(
		nodeType === 1,
		`nodeType has to be undefined or 1, got '${nodeType}'`
	);
	axe.utils.assert(
		typeof nodeName === 'string',
		`nodeName has to be a string, got '${nodeName}'`
	);

	const props = {
		...serialNode,
		nodeType,
		nodeName: nodeName.toLowerCase()
	};
	delete props.attributes;
	return Object.freeze(props);
}

/**
 * Convert between serialised attributes and DOM-like attributes
 * @param {Object} serialNode
 * @return {Object} normalAttributes
 */
function normaliseAttrs({ attributes = {} }) {
	const attrMap = {
		htmlFor: 'for',
		className: 'class'
	};

	return Object.keys(attributes).reduce((attrs, attrName) => {
		const value = attributes[attrName];
		axe.utils.assert(
			typeof value !== 'object' || value === null,
			`expects attributes not to be an object, '${attrName}' was`
		);

		if (value !== undefined) {
			const mappedName = attrMap[attrName] || attrName;
			attrs[mappedName] = value !== null ? String(value) : null;
		}
		return attrs;
	}, {});
}

axe.SerialVirtualNode = SerialVirtualNode;
