var test = require('./helpers/test');

test('ftruncate', function(fs, t) {
	fs.writeFile('/test', new Buffer(1), function() {
		fs.open('/test', 'w', function(err, fd) {
			fs.ftruncate(fd, 10000, function(err) {
				fs.fstat(fd, function(err, stat) {
					t.same(stat.size, 10000);
					fs.ftruncate(fd, 1235, function() {
						fs.fstat(fd, function(err, stat) {
							t.same(stat.size, 1235);
							fs.readFile('/test', function(err, buf) {
								t.same(buf.length, 1235);
								t.end();
							})
						});
					});
				});
			});
		});
	});
});
