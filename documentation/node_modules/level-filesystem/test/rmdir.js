var test = require('./helpers/test');

test('rmdir', function(fs, t) {
	fs.rmdir('/', function(err) {
		t.ok(err);
		t.same(err.code, 'EPERM');

		fs.mkdir('/foo', function() {
			fs.rmdir('/foo', function(err) {
				t.notOk(err);
				fs.rmdir('/foo', function(err) {
					t.ok(err);
					t.same(err.code, 'ENOENT');
					t.end();
				});
			});
		});
	});
});
