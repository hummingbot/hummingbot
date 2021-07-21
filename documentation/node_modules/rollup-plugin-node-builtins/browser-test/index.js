var globals = require('rollup-plugin-node-globals');
var rollup = require( 'rollup' );
var builtins = require('..');
rollup.rollup({
  entry: 'browser-test/main.js',
  plugins: [
    builtins(),
    globals(),
  ]
}).then( function ( bundle ) {
  return bundle.write({
    dest: 'browser-test/dist/bundle.js'
  });
}).then(function () {
  console.log('done');
  process.exit();
}).catch(function (e) {
  console.log('oh noes!');
  console.log(e);
  process.exit(1);
});
