var octal = require('octal')
var test = require('./helpers/test');

test('lchmod', function(fs, t) {
	fs.mkdir('/foo', function() {
		fs.symlink('/foo', '/bar', function() {
			fs.lchmod('/bar', octal(755), function(err) {
				t.notOk(err);
				fs.lstat('/bar', function(err, stat) {
					t.notOk(err);
					t.same(stat.mode, octal(755));
					t.end();
				});
			});
		});
	});
});
