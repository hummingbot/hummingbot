/*exported DqElement */

function truncate(str, maxLength) {
	maxLength = maxLength || 300;

	if (str.length > maxLength) {
		var index = str.indexOf('>');
		str = str.substring(0, index + 1);
	}

	return str;
}

function getSource(element) {
	var source = element.outerHTML;
	if (!source && typeof XMLSerializer === 'function') {
		source = new XMLSerializer().serializeToString(element);
	}
	return truncate(source || '');
}

/**
 * "Serialized" `HTMLElement`. It will calculate the CSS selector,
 * grab the source (outerHTML) and offer an array for storing frame paths
 * @param {HTMLElement} element The element to serialize
 * @param {Object} spec Properties to use in place of the element when instantiated on Elements from other frames
 */
function DqElement(element, options, spec) {
	this._fromFrame = !!spec;

	this.spec = spec || {};
	if (options && options.absolutePaths) {
		this._options = { toRoot: true };
	}

	/**
	 * The generated HTML source code of the element
	 * @type {String}
	 */
	this.source =
		this.spec.source !== undefined ? this.spec.source : getSource(element);

	/**
	 * The element which this object is based off or the containing frame, used for sorting.
	 * Excluded in toJSON method.
	 * @type {HTMLElement}
	 */
	this._element = element;
}

DqElement.prototype = {
	/**
	 * A unique CSS selector for the element
	 * @return {String}
	 */
	get selector() {
		return (
			this.spec.selector || [axe.utils.getSelector(this.element, this._options)]
		);
	},

	/**
	 * Xpath to the element
	 * @return {String}
	 */
	get xpath() {
		return this.spec.xpath || [axe.utils.getXpath(this.element)];
	},

	/**
	 * Direct reference to the `HTMLElement` wrapped by this `DQElement`.
	 */
	get element() {
		return this._element;
	},

	get fromFrame() {
		return this._fromFrame;
	},

	toJSON: function() {
		'use strict';
		return {
			selector: this.selector,
			source: this.source,
			xpath: this.xpath
		};
	}
};

DqElement.fromFrame = function(node, options, frame) {
	node.selector.unshift(frame.selector);
	node.xpath.unshift(frame.xpath);
	return new axe.utils.DqElement(frame.element, options, node);
};

axe.utils.DqElement = DqElement;
