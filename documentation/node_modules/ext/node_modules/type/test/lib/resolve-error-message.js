"use strict";

var assert              = require("chai").assert
  , resolveErrorMessage = require("../../lib/resolve-error-message");

describe("lib/resolve-error-message", function () {
	it("Should insert value", function () {
		assert.equal(resolveErrorMessage("%v is invalid", 12), "12 is invalid");
		assert.equal(resolveErrorMessage("Value is invalid", 12), "Value is invalid");
	});
	it("Should support custom error message via inputOptions.errorMessage", function () {
		assert.equal(
			resolveErrorMessage("%v is invalid", null, { errorMessage: "%v is not supported age" }),
			"null is not supported age"
		);
	});
	it("Should support %n (name) token", function () {
		assert.equal(resolveErrorMessage("%v is invalid", 12, { name: "foo" }), "12 is invalid");
		assert.equal(resolveErrorMessage("%n is invalid", 12, { name: "foo" }), "foo is invalid");
		assert.equal(
			resolveErrorMessage("%v for %n is invalid", 12, { name: "foo" }),
			"12 for foo is invalid"
		);
	});
});
