var fs = require('fs');

/**
 * read() : read(files, fn)
 * Reads from files. If no files are given, read from stdin.
 * The `err` argument will always be null, as errors will be part of `res`.
 *
 *     var read = require('read');
 *     var fnames = process.argv.slice(2); //=> ['readme.txt']
 *
 *     read(fnames, function (err, res) {
 *       res.data    //=> '...'
 *       res.error   //=> undefined | Error()
 *       res.stdin   //=> true | false
 *       res.files   //=> [...]
 *     });
 *
 * You can also iterate through `res.files`.
 *
 *     read(fnames, function (err, res) {
 *       res.files.forEach(function (f) {
 *         f.data    //=> ...
 *         f.error   //=> undefined | Error(...)
 *         f.stdin   //=> true | false
 *         f.name    //=> 'readme.txt'
 *       }
 *     });
 *
 * If `files` is a blank array (or null), data will be read from stdin. The
 * resulting data will have a similar schema.
 *
 *     read([], function (err, res) {
 *       ...
 *     });
 */

function read (files, fn) {
  // from stdin
  if (!files || files.length === 0) {
    read.stdin(function (err, data) {
      if (err)
        fn(null, new Result([{ stdin: true, error: err }]));
      else
        fn(null, new Result([{ stdin: true, data: data }]));
    });
  }
  // from files
  else {
    var out = files.map(function (fname) {
      try {
        var data = fs.readFileSync(fname, 'utf-8');
        return { name: fname, data: data };
      } catch (err) {
        return { name: fname, error: err };
      }
    });

    out = new Result(out);
    fn(null, out);
  }
}

/**
 * read.stdin() : read.stdin(fn)
 * Read data from standard input. The `err` argument will always be null.
 *
 *   read.stdin(function (err, data) {
 *     console.log(data); // string
 *   });
 */

read.stdin = function (fn) {
  var data = '';

  process.stdin.setEncoding('utf8');

  process.stdin.on('readable', function() {
    var chunk = process.stdin.read();
    if (chunk !== null) data += chunk;
  });

  process.stdin.on('end', function() {
    fn(null, data);
  });
};

/**
 * res:
 * The results value is an object passed to the callback of `read()`.
 *
 * ~ data (String): a concatenation of all data in all the files.
 * ~ error (Error): The first error in all files. `undefined` if successful.
 * ~ stdin (Boolean): is `true` if the file is read from stdin
 * ~ files (Array): A list of files.
 *
 * Each of the items in `files` has a similar list of values:
 *
 * ~ data (String): File data
 * ~ error (Error): error, if applicable
 * ~ stdin (Boolean): is `true` if the file is read from stdin
 * ~ name (String): File name
 *
 * See [read()](read) for an example.
 */

function Result(files) {
  this.files = files;
}

getter(Result.prototype, 'data', function () {
  return this.files.map(function (f) { return f.data || ""; }).join("");
});


getter(Result.prototype, 'error', function () {
  return this.files.reduce(function (acc, f) { return acc || f.error; });
});

getter(Result.prototype, 'stdin', function () {
  return this.files && this.files[0] && this.files[0].stdin;
});

/**
 * getter() : getter(prototype, prop, fn)
 * (private) Defines a get property `prop` in the given `prototype` object.
 */

function getter (proto, prop, fn) {
  Object.defineProperty(proto, prop, { get: fn });
}

module.exports = read;
