var test = require('./helpers/test');

test('chown', function(fs, t) {
	fs.mkdir('/foo', function() {
		fs.chown('/foo', 10, 11, function(err) {
			t.notOk(err);
			fs.stat('/foo', function(err, stat) {
				t.notOk(err);
				t.same(stat.uid, 10);
				t.same(stat.gid, 11);
				t.end();
			});
		});
	});
});