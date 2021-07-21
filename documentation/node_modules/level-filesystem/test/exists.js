var test = require('./helpers/test');

test('exists', function(fs, t) {
	fs.exists('/', function(exists) {
		t.ok(exists);
		fs.exists('/foo', function(exists) {
			t.notOk(exists);
			fs.mkdir('/foo', function() {
				fs.exists('/foo', function(exists) {
					t.ok(exists);
					t.end();
				});
			});
		});
	});
});