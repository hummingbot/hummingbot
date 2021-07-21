var test = require('./helpers/test');

test('readlink', function(fs, t) {
	fs.writeFile('/test.txt', 'hello', function(err) {
		fs.symlink('/test.txt', '/foo', function(err) {
			fs.readlink('/foo', function(err, target) {
				t.ok(!err);
				t.same(target, '/test.txt');
				t.end();
			});
 		});
	});
});