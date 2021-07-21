var test = require('./helpers/test');

test('stat root and folder', function(fs, t) {
	fs.stat('/', function(err, stat) {
		t.notOk(err);
		t.ok(stat.isDirectory());
		t.ok(stat.mtime);
		t.ok(stat.ctime);
		t.ok(stat.atime);

		fs.mkdir('/foo', function() {
			fs.stat('/foo', function(err, stat) {
				t.notOk(err);
				t.ok(stat.isDirectory());
				t.end();
			});
		});

	});
});

test('stat not exist', function(fs, t) {
	fs.stat('/foo/bar', function(err) {
		t.ok(err);
		t.same(err.code, 'ENOENT');
		t.end();
	});
});