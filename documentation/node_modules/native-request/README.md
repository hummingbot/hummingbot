# Native Request


Native Request is a simple module that makes you create native node.js requests supports https.

  - supports HTTPS
  - 0 dependencies
  - use callbacks




## Installation

Install the dependencies and devDependencies and start the server.

```code
npm install native-request
```

## Usage

### GET request
 -  request.get(path, headers, callback)
 -  request.get(path, callback)



```js
let request = require('native-request');
request.get('https://github.com', function(err, data, status, headers) {
    if (err) {
        throw err;
    }
    console.log(status); //200
    console.log(data); // page content
    console.log(headers); // response headers
});
```
To add custom **headers** just do like this:
```js
let request = require('native-request');

let headers = {
    "content-type": "plain/text"
}
request.get('https://github.com', headers, function(err, data, status, headers) {
    if (err) {
        throw err;
    }
    console.log(status); //200
    console.log(data); // page content
    console.log(headers); // response headers
});
```
### POST request
 -  request.post(path, callback)
 -  request.post(path, data, callback)
 -  request.post(path, data, headers, callback)

 
To send an empty **post**:
```js
let request = require('native-request');
request.post('https://github.com', function(err, data, status, headers) {
    if (err) {
        throw err;
    }
    console.log(status); //200
    console.log(data); // page content
    console.log(headers); // response headers
});
```

With headers and data:

```js
let request = require('native-request');

let data = {
    "example": true,
}
let headers = {
    "content-type": "plain/text"
}
request.post('https://github.com', data, headers, function(err, data, status, headers) {
    if (err) {
        throw err;
    }
    console.log(status); //200
    console.log(data); // page content
    console.log(headers); // response headers
});
```

### Custom request
 -  *.request(path, method, callback)
 -  *.request(path, method,data, callback)
 -  *.request(path, method, data, headers, callback)
To send a **PUT** request:
```js
let request = require('native-request');
request.request('https://github.com', 'PUT', function(err, data, status, headers) {
    if (err) {
        throw err;
    }
    console.log(status); //200
    console.log(data); // page content
    console.log(headers); // response headers
});
```
With headers and data:
```js
let request = require('native-request');

let data = {
    "example": true,
}
let headers = {
    "content-type": "plain/text"
}
request.request('https://github.com','PUT', data, headers, function(err, data, status, headers) {
    if (err) {
        throw err;
    }
    console.log(status); //200
    console.log(data); // page content
    console.log(headers); // response headers
});
```
### License
MIT. Copyright (c) Samuel Marchese.
