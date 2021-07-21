"use strict";

var assert            = require("chai").assert
  , ensureArrayLength = require("../../array-length/ensure");

describe("array-length/ensure", function () {
	it("Should return coerced value", function () {
		assert.equal(ensureArrayLength("12.23"), 12);
	});
	it("Should crash on no value", function () {
		try {
			ensureArrayLength(-20);
			throw new Error("Unexpected");
		} catch (error) {
			assert.equal(error.name, "TypeError");
			assert.equal(error.message, "-20 is not an array length");
		}
	});
	it("Should provide alternative error message when name option is passed", function () {
		try {
			ensureArrayLength(-20, { name: "foo" });
			throw new Error("Unexpected");
		} catch (error) {
			assert.equal(error.name, "TypeError");
			assert.equal(error.message, "Expected an array length for foo, received -20");
		}
	});
});
