var test = require('./helpers/test');

test('fstat root and folder', function(fs, t) {
	fs.writeFile('/foo', 'bar', function() {
		fs.open('/foo', 'r', function(err, fd) {
			fs.fstat(fd, function(err, stat) {
				t.notOk(err);
				t.ok(stat.size, 3);
				t.end();
			});
		});
	});
});

test('fstat not exist', function(fs, t) {
	fs.fstat(42, function(err) {
		t.ok(err);
		t.same(err.code, 'EBADF');
		t.end();
	});
});