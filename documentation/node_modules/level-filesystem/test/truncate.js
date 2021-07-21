var test = require('./helpers/test');

test('truncate', function(fs, t) {
	fs.writeFile('/test', new Buffer(1), function() {
		fs.truncate('/test', 10000, function(err) {
			fs.stat('/test', function(err, stat) {
				t.same(stat.size, 10000);
				fs.truncate('/test', 1235, function() {
					fs.stat('/test', function(err, stat) {
						t.same(stat.size, 1235);
						fs.readFile('/test', function(err, buf) {
							t.same(buf.length, 1235);
							t.end();
						})
					});
				});
			});
		});
	});
});
