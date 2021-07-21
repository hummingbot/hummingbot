var test = require('./helpers/test');

test('unwatchFile', function(fs, t) {
	t.plan(1);

	fs.watchFile('/test', function() {
		t.ok(true);
	});

	fs.writeFile('/test', new Buffer(1), function() {
		fs.unwatchFile('/test');
		fs.truncate('/test', 10000, function() {
			fs.unlink('/test');
		});
	});
});
