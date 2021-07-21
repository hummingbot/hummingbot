"use strict";

var assert          = require("chai").assert
  , ensureArrayLike = require("../../array-like/ensure");

describe("array-like/ensure", function () {
	it("Should return input value", function () {
		var value = [];
		assert.equal(ensureArrayLike(value), value);
	});
	it("Should allow strings with allowString option", function () {
		var value = "foo";
		assert.equal(ensureArrayLike(value, { allowString: true }), value);
	});
	it("Should crash on invalid value", function () {
		try {
			ensureArrayLike("foo");
			throw new Error("Unexpected");
		} catch (error) {
			assert.equal(error.name, "TypeError");
			assert(error.message.includes("is not an array like"));
		}
	});
	it("Should provide alternative error message when name option is passed", function () {
		try {
			ensureArrayLike("foo", { name: "name" });
			throw new Error("Unexpected");
		} catch (error) {
			assert.equal(error.name, "TypeError");
			assert.equal(error.message, "Expected an array like for name, received foo");
		}
	});
});
