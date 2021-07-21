var test = require('./helpers/test');

test('unlink', function(fs, t) {
	fs.unlink('/test', function(err) {
		t.ok(err);
		t.same(err.code, 'ENOENT');
		fs.writeFile('/test', 'hello', function() {
			fs.unlink('/test', function(err) {
				t.notOk(err);
				fs.exists('/test', function(exists) {
					t.notOk(exists);
					t.end();
				});
			});
		});
	});
});

test('cannot unlink dir', function(fs, t) {
	fs.mkdir('/test', function() {
		fs.unlink('/test', function(err) {
			t.ok(err);
			t.same(err.code, 'EISDIR');
			t.end();
		});
	});
});