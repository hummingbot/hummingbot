"use strict";

var assert       = require("chai").assert
  , ensure       = require("../ensure")
  , ensureNumber = require("../number/ensure");

describe("ensure", function () {
	it("Should support multiple validation datums", function () {
		assert.deepEqual(ensure(["foo", 12.323, ensureNumber], ["bar", 10, ensureNumber]), [
			12.323, 10
		]);
	});
	it("Should surface only error", function () {
		try {
			ensure(["foo", null, ensureNumber], ["bar", 10, ensureNumber]);
		} catch (error) {
			assert.equal(error.name, "TypeError");
			assert.equal(error.message, "Expected a number for foo, received null");
		}
	});
	it("Should surface only error", function () {
		try {
			ensure(["foo", null, ensureNumber], ["bar", 10, ensureNumber]);
		} catch (error) {
			assert.equal(error.name, "TypeError");
			assert.equal(error.message, "Expected a number for foo, received null");
		}
	});
	it("Should cumulate errors", function () {
		try {
			ensure(["foo", null, ensureNumber], ["bar", NaN, ensureNumber]);
		} catch (error) {
			assert.equal(error.name, "TypeError");
			assert.equal(
				error.message,
				"Approached following errors:" +
					"\n - Expected a number for foo, received null" +
					"\n - Expected a number for bar, received NaN"
			);
		}
	});
	it("Should support Error from global options", function () {
		try {
			ensure(["foo", null, ensureNumber], ["bar", NaN, ensureNumber], { Error: RangeError });
		} catch (error) {
			assert.equal(error.name, "RangeError");
			assert.equal(
				error.message,
				"Approached following errors:" +
					"\n - Expected a number for foo, received null" +
					"\n - Expected a number for bar, received NaN"
			);
		}
		try {
			ensure(["foo", null, ensureNumber], ["bar", 10, ensureNumber], { Error: RangeError });
		} catch (error) {
			assert.equal(error.name, "RangeError");
			assert.equal(error.message, "Expected a number for foo, received null");
		}
	});
	it("Should support individual validation options", function () {
		try {
			ensure(["foo", null, ensureNumber, { Error: RangeError }], ["bar", 10, ensureNumber]);
		} catch (error) {
			assert.equal(error.name, "RangeError");
			assert.equal(error.message, "Expected a number for foo, received null");
		}
	});
});
