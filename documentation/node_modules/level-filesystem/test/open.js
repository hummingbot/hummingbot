var test = require('./helpers/test');

test('open', function(fs, t) {
	fs.open('/test', 'w', function(err, fd) {
		t.ok(!err);
		t.same(typeof fd, 'number');
		t.end()
	});
});

test('open not exist', function(fs, t) {
	fs.open('/test', 'r', function(err, fd) {
		t.ok(err);
		t.same(err.code, 'ENOENT');
		fs.open('/test', 'w', function(err, fd) {
			t.ok(!err);
			t.same(typeof fd, 'number');
			t.end()
		});
	});
});

test('open w+', function(fs, t) {
	fs.open('/test', 'w+', function(err, fd) {
		t.ok(!err);
		t.same(typeof fd, 'number');

		fs.stat('/test', function(err, stat) {
			t.ok(!err);
			t.end();
		});
	});
});
