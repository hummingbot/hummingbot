var test = require('./helpers/test');
var concat = require('concat-stream');

test('createReadStream', function(fs, t) {
	fs.writeFile('/test.txt', 'hello', function(err) {
		var rs = fs.createReadStream('/test.txt');
		rs.pipe(concat(function(data) {
			t.same(data, new Buffer('hello'));
			t.end();
		}))
	});
});

test('createReadStream big file', function(fs, t) {
	var big = new Buffer(100 * 1024);

	fs.writeFile('/test.txt', big, function(err) {
		var rs = fs.createReadStream('/test.txt');
		rs.pipe(concat(function(data) {
			t.same(data, big);
			t.end();
		}))
	});
});

test('createReadStream random access', function(fs, t) {
	fs.writeFile('/test.txt', 'hello world', function(err) {
		var rs = fs.createReadStream('/test.txt', {
			start: 2,
			end: 5
		});
		rs.pipe(concat(function(data) {
			t.same(data, new Buffer('llo '));
			t.end();
		}))
	});
});

test('createReadStream enoent', function(fs, t) {
	var rs = fs.createReadStream('/test.txt');

	rs.on('error', function(err) {
		t.same(err.code, 'ENOENT');
		t.ok(true);
		t.end();
	});
});