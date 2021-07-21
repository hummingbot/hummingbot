var test = require('./helpers/test');

test('utimes', function(fs, t) {
	fs.mkdir('/foo', function() {
		fs.utimes('/foo', new Date(0), new Date(0), function(err) {
			t.notOk(err);
			fs.stat('/foo', function(err, stat) {
				t.same(stat.atime.getTime(), 0);
				t.same(stat.mtime.getTime(), 0);

				fs.utimes('/foo', new Date(10000), new Date(20000), function(err) {
					t.notOk(err);
					fs.stat('/foo', function(err, stat) {
						t.same(stat.atime.getTime(), 10000);
						t.same(stat.mtime.getTime(), 20000);
						t.end();
					});
				});
			});
		});
	});
});