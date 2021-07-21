"use strict";

var assert              = require("chai").assert
  , ensureNaturalNumber = require("../../natural-number/ensure");

describe("natural-number/ensure", function () {
	it("Should return coerced value", function () {
		assert.equal(ensureNaturalNumber("12.23"), 12);
	});
	it("Should crash on no value", function () {
		try {
			ensureNaturalNumber(-20);
			throw new Error("Unexpected");
		} catch (error) {
			assert.equal(error.name, "TypeError");
			assert.equal(error.message, "-20 is not a natural number");
		}
	});
	it("Should provide alternative error message when name option is passed", function () {
		try {
			ensureNaturalNumber(-20, { name: "name" });
			throw new Error("Unexpected");
		} catch (error) {
			assert.equal(error.name, "TypeError");
			assert.equal(error.message, "Expected a natural number for name, received -20");
		}
	});
	it("Should support min validation", function () {
		try {
			ensureNaturalNumber(2, { min: 3 });
			throw new Error("Unexpected");
		} catch (error) {
			assert.equal(error.name, "TypeError");
			assert.equal(error.message, "2 is not greater or equal 3");
		}
	});
});
