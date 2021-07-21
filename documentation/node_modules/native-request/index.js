`use strict`

const http = require('http');
const https = require('https');
const url = require('url');

function getProtocol(path) {
	return url.parse(path).protocol === "http:" ? http : https;
}

/**
 * Send a get request
 * @param path is the url endpoint
 * @param headers of the request
 * @param callback contains (error, body, status, headers)
 */
 function get(path, headers, callback) {
 	request(path, "GET", null, headers, callback);
 }

/**
 * Send a post request
 * @param path is the url endpoint
 * @param headers of the request
 * @param callback contains (error, body, status, headers)
 * @param data a JSON Object or a string
 */
 function post(path, data, headers, callback) {
 	request(path, "POST", data, headers, callback);
 }

/**
 * Send a custom request
 * @param path is the url endpoint
 * @param headers of the request
 * @param callback contains (error, statusCode, data)
 * @param data a JSON Object or a string
 * @param method is the protocol used like POST GET DELETE PUT etc...
 */
 function request(path, method, data, headers = '', callback) {
 	if (typeof data === 'function') {
 		callback = data;
 		data = '';
 	} else if (typeof headers === 'function') {
 		callback = headers;
 		headers = {};
 	} 
 	const postData = typeof data === "object" ? JSON.stringify(data) : data;
 	const parsedUrl = url.parse(path);
 	const options = {
 		hostname: parsedUrl.hostname,
 		port: parsedUrl.port,
 		path: parsedUrl.pathname +  (!!parsedUrl.search ? parsedUrl.search : ''),
  		method: method,
 		headers: headers
 	};
 	const req = getProtocol(path).request(options, function (response) {
 		handleResponse(response, callback);
 	});
 	req.on('error', function (error) {
 		callback(error);
 		console.error(error);
 	});
	// Write data to request body
	if (method !== "GET")
		req.write(postData);
	req.end();
}

function handleResponse(response, callback) {
	let body = '';
	const status = response.statusCode;
	const hasError = status >= 300;
	response.setEncoding('utf8');
	response.on('data', function (data) {
		body += data;
	});
	response.on('end', function () {
		callback(hasError ? body : null, hasError ? null : body, response.statusCode, response.headers);
	});
}

module.exports = {
	get,
	request,
	post
};
