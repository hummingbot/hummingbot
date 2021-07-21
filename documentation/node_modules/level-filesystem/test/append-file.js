var test = require('./helpers/test');

test('appendFile', function(fs, t) {
	fs.writeFile('/test.txt', 'hello', function(err) {
		fs.appendFile('/test.txt', ' world', function(err) {
			t.notOk(err);
			fs.readFile('/test.txt', function(err, data) {
				t.same(data.toString(), 'hello world');
				t.end();
			});
		});
	});
});