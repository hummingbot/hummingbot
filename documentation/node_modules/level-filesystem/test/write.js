var test = require('./helpers/test');

test('write', function(fs, t) {
	fs.open('/test', 'w', function(err, fd) {
		fs.write(fd, new Buffer('hello world'), 0, 11, null, function(err, written, buf) {
			t.ok(!err);
			t.ok(buf);
			t.same(written, 11);
			fs.close(fd, function() {
				fs.readFile('/test', 'utf-8', function(err, buf) {
					t.same(buf, 'hello world');
					t.end();
				});
			});
		});
	});
});

test('write + partial', function(fs, t) {
	fs.open('/test', 'w', function(err, fd) {
		fs.write(fd, new Buffer('hello'), 0, 5, null, function(err, written, buf) {
			fs.write(fd, new Buffer(' world'), 0, 6, null, function(err, written, buf) {
				t.ok(!err);
				t.ok(buf);
				t.same(written, 6);
				fs.close(fd, function() {
					fs.readFile('/test', 'utf-8', function(err, buf) {
						t.same(buf, 'hello world');
						t.end();
					});
				});
			});
		});
	});
});

test('write + pos', function(fs, t) {
	fs.open('/test', 'w', function(err, fd) {
		fs.write(fd, new Buffer('111111'), 0, 6, 0, function() {
			fs.write(fd, new Buffer('222222'), 0, 5, 0, function() {
				fs.write(fd, new Buffer('333333'), 0, 4, 0, function() {
					fs.write(fd, new Buffer('444444'), 0, 3, 0, function() {
						fs.write(fd, new Buffer('555555'), 0, 2, 0, function() {
							fs.write(fd, new Buffer('666666'), 0, 1, 0, function() {
								fs.close(fd, function() {
									fs.readFile('/test', 'utf-8', function(err, buf) {
										t.same(buf, '654321');
										t.end();
									});
								});
							});
						});
					});
				});
			});
		});
	});
});

test('write + append', function(fs, t) {
	fs.writeFile('/test', 'hello world', function() {
		fs.open('/test', 'a', function(err, fd) {
			fs.write(fd, new Buffer(' world'), 0, 6, null, function() {
				fs.close(fd, function() {
					fs.readFile('/test', 'utf-8', function(err, buf) {
						t.same(buf, 'hello world world');
						t.end();
					});
				});
			});
		});
	});
});