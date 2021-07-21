var test = require('./helpers/test');

test('futimes', function(fs, t) {
	fs.writeFile('/foo', 'bar', function() {
		fs.open('/foo', 'r', function(err, fd) {
			fs.futimes(fd, new Date(0), new Date(0), function(err) {
				t.notOk(err);
				fs.fstat(fd, function(err, stat) {
					t.same(stat.atime.getTime(), 0);
					t.same(stat.mtime.getTime(), 0);

					fs.futimes(fd, new Date(10000), new Date(20000), function(err) {
						t.notOk(err);
						fs.fstat(fd, function(err, stat) {
							t.same(stat.atime.getTime(), 10000);
							t.same(stat.mtime.getTime(), 20000);
							t.end();
						});
					});
				});
			});
		});
	});
});