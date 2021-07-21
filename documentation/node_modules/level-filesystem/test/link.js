var test = require('./helpers/test');

test('link', function(fs, t) {
	fs.writeFile('/test.txt', 'hello', function(err) {
		fs.link('/test.txt', '/foo', function(err) {
			t.ok(!err);
			fs.readFile('/foo', function(err, data) {
				t.same(data.toString(), 'hello');
 				fs.stat('/foo', function(err, stat) {
					t.same(stat.mode, 0666);
 					t.same(stat.size, 5);
					t.ok(stat.isFile());
					t.end();
 				});
			});
 		});
	});
});

test('link + unlink', function(fs, t) {
	fs.writeFile('/test.txt', 'hello', function(err) {
		fs.link('/test.txt', '/foo', function(err) {
			t.ok(!err);
			fs.unlink('/test.txt', function() {
				fs.readFile('/foo', function(err, data) {
					t.same(data.toString(), 'hello');
	 				fs.stat('/foo', function(err, stat) {
						t.same(stat.mode, 0666);
	 					t.same(stat.size, 5);
						t.ok(stat.isFile());
						t.end();
	 				});
				});
			});
 		});
	});
});

test('link + unlink twice', function(fs, t) {
	fs.writeFile('/test.txt', 'hello', function(err) {
		fs.link('/test.txt', '/foo', function(err) {
			t.ok(!err);
			fs.unlink('/test.txt', function() {
				fs.unlink('/foo', function() {
					fs.writeFile('/test.txt', 'a', {flag:'a'}, function() {
						fs.readFile('/test.txt', function(err, data) {
							t.same(data.toString(), 'a');
							t.end();
						});
					});
				});
			});
 		});
	});
});