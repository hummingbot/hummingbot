var test = require('./helpers/test');

test('readFile', function(fs, t) {
	fs.writeFile('/test.txt', 'hello', function(err) {
		fs.readFile('/test.txt', function(err, data) {
			t.notOk(err);
			t.ok(Buffer.isBuffer(data));
			t.same(data.toString(), 'hello');
			t.end();
		});
	});
});

test('readFile + encoding', function(fs, t) {
	fs.writeFile('/foo', 'hello', function(err) {
		fs.readFile('/foo', 'hex', function(err, data) {
			t.notOk(err);
			t.same(data, '68656c6c6f');
			t.end();
		});
	});
});

test('cannot readFile dir', function(fs, t) {
	fs.mkdir('/test', function() {
		fs.readFile('/test', function(err) {
			t.ok(err);
			t.same(err.code, 'EISDIR');
			t.end();
		});
	});
});