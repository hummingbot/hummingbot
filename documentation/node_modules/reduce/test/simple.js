'use strict';

var test = require('tape');
var reduce = require('..');

var createItem = function createTestItem() {
    return {
        a: 'a1',
        b: 'b1',
        c: 'c1'
    };
};

test('reduce calls each iterator', function (t) {
    var item = createItem();
    var timesCalled = 0;
    var accumulator = { key: '' };
    var expectedKeys = ['a', 'b', 'c'];
    var expectedValues = ['a1', 'b1', 'c1'];
    var expectedAccumulatorKeys = ['', 'a1', 'a1b1', 'a1b1c1'];
    var calledArguments = [];
    var slice = Array.prototype.slice;
    var iterator = function (acc, value, key, list) {
        var expectedKey = expectedKeys[timesCalled];
        var expectedValue = expectedValues[timesCalled];
        var expectedAccumulatorKey = expectedAccumulatorKeys[timesCalled];

        calledArguments.push(slice.apply(arguments));

        t.equal(value, expectedValue, 'value ' + value + ' does not match ' + expectedValue);
        t.equal(key, expectedKey, 'key ' + key + ' does not match ' + expectedKey);
        t.equal(list, item, 'list arg is not correct');
        t.equal(acc.key, expectedAccumulatorKey, 'accumulator key ' + acc.key + ' does not match ' + expectedAccumulatorKey);

        timesCalled += 1;
        acc.key += value;
        return acc;
    };

    var result = reduce(item, iterator, accumulator);

    t.equal(timesCalled, 3, 'iterator was not called thrice');
    t.deepEqual(result, { key: 'a1b1c1' }, 'result is incorrect');

    t.deepEqual(calledArguments[0], [{
        key: 'a1b1c1'
    }, 'a1', 'a', item], 'iterator called with wrong arguments');
    t.deepEqual(calledArguments[1], [{
        key: 'a1b1c1'
    }, 'b1', 'b', item], 'iterator called with wrong arguments');
    t.deepEqual(calledArguments[2], [{
        key: 'a1b1c1'
    }, 'c1', 'c', item], 'iterator called with wrong arguments');
    t.deepEqual(result, {
        key: 'a1b1c1'
    });

    t.end();
});

test('reduce calls iterator with correct this value', function (t) {
    var item = createItem();
    var thisValue = {};
    var iterator = function () {
        // eslint-disable-next-line no-invalid-this
        t.equal(this, thisValue, 'this value is incorrect');
    };

    reduce(item, iterator, thisValue, {});

    t.end();
});

test('reduce reduces with first value if no initialValue', function (t) {
    var list = [1, 2];
    var iterator = function (sum, v) {
        return sum + v;
    };

    var result = reduce(list, iterator);

    t.equal(result, 3, 'result is incorrect');

    t.end();
});

test('reduce throws a TypeError when an invalid iterator is provided', function (t) {
    t['throws'](function () { reduce([1, 2]); }, TypeError, 'requires a function');

    t.end();
});

test('reduce has a length of 2, mimicking spec', function (t) {
    t.equal(reduce.length, 2, 'reduce has a length of 2');

    t.end();
});
