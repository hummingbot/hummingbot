var octal = require('octal')
var test = require('./helpers/test');

test('mkdir', function(fs, t) {
	fs.mkdir('/foo/bar', function(err) {
		t.ok(err);
		t.same(err.code, 'ENOENT');

		fs.mkdir('/foo', function(err) {
			t.notOk(err);

			fs.mkdir('/foo', function(err) {
				t.ok(err);
				t.same(err.code, 'EEXIST');

				fs.mkdir('/foo/bar', function(err) {
					t.notOk(err);
					t.end();
				});
			});
		});
	});
});

test('mkdir + stat', function(fs, t) {
	fs.mkdir('/foo', function() {
		fs.stat('/foo', function(err, stat) {
			t.notOk(err);
			t.same(stat.mode, octal(777));
			t.ok(stat.isDirectory());
			t.end();
		});
	});
});

test('mkdir with modes', function(fs, t) {
	fs.mkdir('/foo', 0766, function() {
		fs.stat('/foo', function(err, stat) {
			t.notOk(err);
			t.same(stat.mode, 0766);
			t.ok(stat.isDirectory());
			t.end();
		});
	});
});
