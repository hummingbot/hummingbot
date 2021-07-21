var test = require('./helpers/test');

test('fchmod', function(fs, t) {
	fs.writeFile('/foo', 'bar', function() {
		fs.open('/foo', 'r', function(err, fd) {
			fs.fchmod(fd, 0655, function(err) {
				t.notOk(err);
				fs.stat('/foo', function(err, stat) {
					t.notOk(err);
					t.same(stat.mode, 0655);
					t.end();
				});
			});
		});
	});
});