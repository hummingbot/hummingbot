"use strict";

var assert      = require("chai").assert
  , ensureError = require("../../error/ensure");

describe("error/ensure", function () {
	it("Should return input value", function () {
		var value = new Error();
		assert.equal(ensureError(value), value);
	});
	it("Should crash on invalid value", function () {
		try {
			ensureError(null);
			throw new Error("Unexpected");
		} catch (error) {
			assert.equal(error.name, "TypeError");
			assert(error.message.includes("is not an error"));
		}
	});
	it("Should provide alternative error message when name option is passed", function () {
		try {
			ensureError(null, { name: "name" });
			throw new Error("Unexpected");
		} catch (error) {
			assert.equal(error.name, "TypeError");
			assert.equal(error.message, "Expected an error for name, received null");
		}
	});
});
