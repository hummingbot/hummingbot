'use strict';

var test = require('tape');
var stringify = require('../');
var tests = require('../benchmark/test.json');
var expect = require('chai').expect;

for (var i = 0; i < tests.length; i++) {
    var json = tests[i];

    test('Benchmark - ' + i, function (t) {
        var str = stringify(json);
        var str2 = JSON.stringify(json);
        var back = JSON.parse(str);
        var back2 = JSON.parse(str2);
        expect(back).to.eql(json);
        expect(back2).to.eql(json);
        t.end();
    });
}
