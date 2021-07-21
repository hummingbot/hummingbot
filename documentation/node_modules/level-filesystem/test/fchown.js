var test = require('./helpers/test');

test('fchown', function(fs, t) {
	fs.writeFile('/foo', 'bar', function() {
		fs.open('/foo', 'r', function(err, fd) {
			fs.fchown(fd, 10, 11, function(err) {
				t.notOk(err);
				fs.stat('/foo', function(err, stat) {
					t.notOk(err);
					t.same(stat.uid, 10);
					t.same(stat.gid, 11);
					t.end();
				});
			});
		});
	});
});