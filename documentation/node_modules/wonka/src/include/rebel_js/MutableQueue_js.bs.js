

import * as Curry from "bs-platform/lib/es6/curry.js";

function isEmpty(q) {
  return q.length === 0;
}

function reduceU(q, accu, f) {
  return q.reduce((function (acc, x) {
                return f(acc, x);
              }), accu);
}

function reduce(q, accu, f) {
  return q.reduce(Curry.__2(f), accu);
}

function transfer(q1, q2) {
  Array.prototype.push.apply(q1, q2);
  q1.length = 0;
  
}

export {
  isEmpty ,
  reduceU ,
  reduce ,
  transfer ,
  
}
/* No side effect */
