"use strict";

var isValue             = require("../value/is")
  , resolveErrorMessage = require("./resolve-error-message");

module.exports = function (value, defaultMessage, inputOptions) {
	if (inputOptions && !isValue(value)) {
		if ("default" in inputOptions) return inputOptions["default"];
		if (inputOptions.isOptional) return null;
	}
	var ErrorConstructor = (inputOptions && inputOptions.Error) || TypeError;
	throw new ErrorConstructor(resolveErrorMessage(defaultMessage, value, inputOptions));
};
