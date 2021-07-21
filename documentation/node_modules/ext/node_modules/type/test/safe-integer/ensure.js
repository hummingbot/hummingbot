"use strict";

var assert            = require("chai").assert
  , ensureSafeInteger = require("../../safe-integer/ensure");

describe("safe-integer/ensure", function () {
	it("Should return coerced value", function () {
		assert.equal(ensureSafeInteger("12.23"), 12);
	});
	it("Should crash on no value", function () {
		try {
			ensureSafeInteger(null);
			throw new Error("Unexpected");
		} catch (error) {
			assert.equal(error.name, "TypeError");
			assert.equal(error.message, "null is not a safe integer");
		}
	});
	it("Should provide alternative error message when name option is passed", function () {
		try {
			ensureSafeInteger(null, { name: "name" });
			throw new Error("Unexpected");
		} catch (error) {
			assert.equal(error.name, "TypeError");
			assert.equal(error.message, "Expected a safe integer for name, received null");
		}
	});
});
