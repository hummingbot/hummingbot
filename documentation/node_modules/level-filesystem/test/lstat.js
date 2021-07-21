var test = require('./helpers/test');

test('lstat', function(fs, t) {
	fs.writeFile('/test.txt', 'hello', function(err) {
		fs.symlink('/test.txt', '/foo', function(err) {
			fs.lstat('/foo', function(err, stat) {
				t.ok(!err);
				t.ok(stat.isSymbolicLink());
				t.end();
			});
 		});
	});
});
