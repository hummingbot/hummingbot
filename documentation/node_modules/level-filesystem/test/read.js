var test = require('./helpers/test');

test('read', function(fs, t) {
	fs.writeFile('/test', 'hello worldy world', function() {
		fs.open('/test', 'r', function(err, fd) {
			var b = new Buffer(1024);
			fs.read(fd, b, 0, 11, null, function(err, read) {
				t.ok(!err);
				t.same(read, 11);
				t.same(b.slice(0, 11), new Buffer('hello world'))
				fs.read(fd, b, 0, 11, null, function(err, read) {
					t.ok(!err);
					t.same(read, 7);
					t.same(b.slice(0, 11), new Buffer('y worldorld'));
					t.end();
				});
			});
		});
	});
});

test('read', function(fs, t) {
	fs.writeFile('/test', 'hello worldy world', function() {
		fs.open('/test', 'r', function(err, fd) {
			var b = new Buffer(1024);
			fs.read(fd, b, 0, 11, 0, function(err, read) {
				t.ok(!err);
				t.same(read, 11);
				t.same(b.slice(0, 11), new Buffer('hello world'))
				fs.read(fd, b, 0, 11, 1, function(err, read) {
					t.ok(!err);
					t.same(read, 11);
					t.same(b.slice(0, 11), new Buffer('ello worldy'));
					t.end();
				});
			});
		});
	});
});