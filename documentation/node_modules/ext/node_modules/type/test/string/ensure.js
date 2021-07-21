"use strict";

var assert       = require("chai").assert
  , ensureString = require("../../string/ensure");

describe("string/ensure", function () {
	it("Should return coerced value", function () { assert.equal(ensureString(12), "12"); });
	it("Should crash on no value", function () {
		try {
			ensureString(null);
			throw new Error("Unexpected");
		} catch (error) {
			assert.equal(error.name, "TypeError");
			assert.equal(error.message, "null is not a string");
		}
	});
	it("Should provide alternative error message when name option is passed", function () {
		try {
			ensureString(null, { name: "name" });
			throw new Error("Unexpected");
		} catch (error) {
			assert.equal(error.name, "TypeError");
			assert.equal(error.message, "Expected a string for name, received null");
		}
	});
});
