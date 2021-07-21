var test = require('./helpers/test');

test('lchown', function(fs, t) {
	fs.mkdir('/foo', function() {
		fs.symlink('/foo', '/bar', function() {
			fs.lchown('/bar', 10, 11, function(err) {
				t.notOk(err);
				fs.lstat('/bar', function(err, stat) {
					t.notOk(err);
					t.same(stat.uid, 10);
					t.same(stat.gid, 11);
					t.end();
				});
			});
		});
	});
});