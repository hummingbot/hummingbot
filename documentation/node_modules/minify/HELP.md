Minify
===============
[NPM_INFO_IMG]:             https://nodei.co/npm/minify.png?stars

[Minify](http://coderaiser.github.io/minify "Minify") - a minifier of js, css, html and img files,
used in [Cloud Commander](http://cloudcmd.io "Cloud Commander") project.

To use `minify` as middleware try [Mollify](https://github.com/coderaiser/node-mollify "Mollify").

Install
---------------
![NPM_INFO][NPM_INFO_IMG]

You can install minify via [npm](https://www.npmjs.org/):

```
npm i minify -g
```

Command Line
---------------
Command line syntax:

```
minify <input-file1> <input-file2> <input-fileN> > output
stdout | minify --<flag>
```
For example:

```
minify client.js util.js > all.js
minify screen.css reset.css > all.css

cat client.js | minify --js
cat *.css | minify --css
```

API
---------------
The **Minify** module contains an api for interacting with other js files.


```js
minify = require('minify');
```
After minification, a file will be saved in the temporary directory.

minify - function to minificate js, html and css-files.

 - **file**                 - path to file.
 - **options**(optional)    - object contains options.
 - **callback**

Possible options:
 - **name**
 - **stream**

**Examples**:

## Optimize file
```js
var minify = require('minify');

minify('client.js', 'name', function(error, name) {
    console.log(error || name);
});
```

```js
minify('client.js', 'stream', function(error, stream) {
    var streamWrite = fs.createWriteStream('client.min.js');
    
    if (error)
        console.error(error.message);
    else
        stream.pipe(streamWrite);
});
```

if post processing is need: 

```js
minify('client.js', function(error, data) {

});
```

## Optimize data

Parameters:
- Data
- Callback

**Example**:

```js
minify.js('function hello() { if (2 > 3) console.log(\'for real\')}', function(error, data) {
    console.log(error, data);
});

minify.css('div { color: #000000}', function(error, data) {
    console.log(error, data);
});

```

## Express middleware

To use as express middleware [mollify](https://github.com/coderaiser/node-mollify Mollify) could be used.

License
---------------

MIT
