let request = require('../index');
let http = require('http');
let assert = require('assert');

const server = http.createServer(function(request, response) {
    var body = ''
    request.on('data', function(data) {
      body += data
    })
    request.on('end', function() {
      response.writeHead(200, {'Content-Type': 'text/html'})
      response.end(body)
    })
  });


describe('/POST', function () {
	before(function () {
		server.listen(8000);
	});


	describe('/', function () {
		it('should return 200', function (done) {
			request.post('http://localhost:8000/',function(err, data, status) {
				assert.ifError(err);
				assert.equal(200, status);
				done();
			});
		});

		it('should say "Hello, world!" inside a JSON object', function (done) {
			request.post("http://localhost:8000",  {hello: 'Hello, world!'}, function(err, data) {
				assert.ifError(err);
				assert.deepEqual({hello: 'Hello, world!'}, JSON.parse(data));	
				done();
			});
		});

		it("should have content-type to 'text/html'", function (done) {
			request.post("http://localhost:8000", function(err, data, status, headers) {
				assert.ifError(err);
				assert.equal('text/html' , headers['content-type']);
				done();
			});
		});
	});

	after(function () {
		server.close();
	});
});

