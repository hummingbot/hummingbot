"use strict";

var assert         = require("chai").assert
  , ensureFunction = require("../../function/ensure");

describe("function/ensure", function () {
	it("Should return input value", function () {
		var value = function () { return true; };
		assert.equal(ensureFunction(value), value);
	});
	it("Should crash on invalid value", function () {
		try {
			ensureFunction(null);
			throw new Error("Unexpected");
		} catch (error) {
			assert.equal(error.name, "TypeError");
			assert(error.message.includes("is not a function"));
		}
	});
	it("Should provide alternative error message when name option is passed", function () {
		try {
			ensureFunction(null, { name: "name" });
			throw new Error("Unexpected");
		} catch (error) {
			assert.equal(error.name, "TypeError");
			assert.equal(error.message, "Expected a function for name, received null");
		}
	});
});
