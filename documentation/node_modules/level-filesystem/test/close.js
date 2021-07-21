var test = require('./helpers/test');

test('close', function(fs, t) {
	fs.open('/test', 'w', function(err, fd) {
		t.ok(!err);
		fs.close(fd, function(err) {
			t.ok(!err);
			fs.fsync(fd, function(err) {
				t.ok(err);
				t.same(err.code, 'EBADF');
				t.end();
			})
		});
	});
});
