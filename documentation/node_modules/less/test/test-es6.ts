// https://github.com/less/less.js/issues/3533
console.log('Testing ES6 imports...')

import less from '..';
let lessRender = less.render;

// then I call lessRender on something
let y = lessRender(`
body {
    a: 1;
    b: 2;
    c: 30;
    d: 4;
}`, {sourceMap: {}},  function(error, output) {
  if (error)
    console.error(error)
})