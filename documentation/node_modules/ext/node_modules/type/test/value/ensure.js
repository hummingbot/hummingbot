"use strict";

var assert      = require("chai").assert
  , ensureValue = require("../../value/ensure");

describe("value/ensure", function () {
	it("Should return input value", function () {
		var value = {};
		assert.equal(ensureValue(value), value);
	});
	it("Should crash on no value", function () {
		try {
			ensureValue(null);
			throw new Error("Unexpected");
		} catch (error) {
			assert.equal(error.name, "TypeError");
			assert.equal(error.message, "Cannot use null");
		}
	});
	it("Should provide alternative error message when name option is passed", function () {
		try {
			ensureValue(null, { name: "name" });
			throw new Error("Unexpected");
		} catch (error) {
			assert.equal(error.name, "TypeError");
			assert.equal(error.message, "Expected a value for name, received null");
		}
	});
});
