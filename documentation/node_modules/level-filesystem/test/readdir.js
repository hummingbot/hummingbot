var test = require('./helpers/test');

test('readdir', function(fs, t) {
	fs.readdir('/', function(err, list) {
		t.notOk(err);
		t.same(list, []);

		fs.readdir('/foo', function(err, list) {
			t.ok(err);
			t.notOk(list);
			t.same(err.code, 'ENOENT');

			fs.mkdir('/foo', function() {
				fs.readdir('/', function(err, list) {
					t.notOk(err);
					t.same(list, ['foo']);

					fs.readdir('/foo', function(err, list) {
						t.notOk(err);
						t.same(list, []);
						t.end();
					});
				});
			});
		});
	});
});

test('readdir not recursive', function(fs, t) {
	fs.mkdir('/foo', function() {
		fs.mkdir('/foo/bar', function() {
			fs.mkdir('/foo/bar/baz', function() {
				fs.readdir('/foo', function(err, list) {
					t.notOk(err);
					t.same(list, ['bar']);
					fs.readdir('/foo/bar', function(err, list) {
						t.notOk(err);
						t.same(list, ['baz']);
						t.end();
					});
				});
			});
		});
	});
});