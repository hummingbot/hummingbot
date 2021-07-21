let request = require('../index');
let http = require('http');
let assert = require('assert');
let server = http.createServer(function (req, res) {
	res.writeHead(200, { 'content-type': 'text/plain' });
	res.end('Hello, world!\n');
});


describe('/GET', function () {
	before(function () {
		server.listen(8000);
	});


	describe('/', function () {
		it('should return 200', function (done) {
			request.get('http://localhost:8000/?hey=d', function(err, data, status, headers) {
				assert.ifError(err);
				assert.equal(200, status);
				done();
			});
		});

		it('should say "Hello, world!"', function (done) {
			request.get("http://localhost:8000", function(err, data, status, headers) {
				assert.ifError(err);
				assert.equal('Hello, world!\n', data);	
				done();
			});
		});	

		it("should have content-type to 'text/plain'", function (done) {
			request.get("http://localhost:8000",function(err, data, status, headers) {
				assert.ifError(err);
				assert.equal('text/plain' , headers['content-type']);
				done();
			});
		});
	});

	after(function () {
		server.close();
	});
});

