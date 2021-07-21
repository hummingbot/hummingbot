"use strict";

var assert       = require("chai").assert
  , ensureObject = require("../../object/ensure");

describe("object/ensure", function () {
	it("Should return input value", function () {
		var value = {};
		assert.equal(ensureObject(value), value);
	});
	it("Should crash on no value", function () {
		try {
			ensureObject(null);
			throw new Error("Unexpected");
		} catch (error) {
			assert.equal(error.name, "TypeError");
			assert.equal(error.message, "null is not an object");
		}
	});
	it("Should provide alternative error message when name option is passed", function () {
		try {
			ensureObject(null, { name: "name" });
			throw new Error("Unexpected");
		} catch (error) {
			assert.equal(error.name, "TypeError");
			assert.equal(error.message, "Expected an object for name, received null");
		}
	});
});
