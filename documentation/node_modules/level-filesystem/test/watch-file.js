var test = require('./helpers/test');

test('watchFile', function(fs, t) {
	t.plan(3);

	fs.watchFile('/test', function() {
		t.ok(true);
	});

	fs.writeFile('/test', new Buffer(1), function() {
		fs.truncate('/test', 10000, function(err) {
			fs.unlink('/test');
		});
	});
});
