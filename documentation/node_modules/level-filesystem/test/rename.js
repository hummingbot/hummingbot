var test = require('./helpers/test');

test('rename', function(fs, t) {
	fs.mkdir('/foo', function() {
		fs.rename('/foo', '/bar', function(err) {
			t.notOk(err);

			fs.readdir('/', function(err, list) {
				t.notOk(err);
				t.same(list, ['bar']);
				t.end();
			});
		});
	});
});

test('rename to non empty dir', function(fs, t) {
	fs.mkdir('/foo', function() {
		fs.mkdir('/bar', function() {
			fs.mkdir('/bar/baz', function() {
				fs.rename('/foo', '/bar', function(err) {
					t.ok(err);
					t.same(err.code, 'ENOTEMPTY');

					fs.readdir('/', function(err, list) {
						t.notOk(err);
						t.same(list.sort(), ['bar', 'foo']);
						t.end();
					});
				});
			});
		});
	});
});