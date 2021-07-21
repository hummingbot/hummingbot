const fs = require('fs');
const constants = require('constants');
const path = require('path');

var out = fs.createWriteStream(path.join(__dirname, 'dist', 'constants.js'));

Object.keys(constants).forEach(function (key) {
  var value = constants[key];
  out.write(`export var ${key} = ${JSON.stringify(value)};\n`);
});
out.write('export default {\n  ');
Object.keys(constants).forEach(function (key, i) {
  if (i) {
    out.write(',\n  ')
  }
  out.write(`${key}: ${key}`);
});
out.end('\n};\n');
