

import * as Belt_MutableQueue from "bs-platform/lib/es6/belt_MutableQueue.js";

function addMany(q1, q2) {
  return Belt_MutableQueue.transfer(Belt_MutableQueue.copy(q1), q2);
}

var fromArray = Belt_MutableQueue.fromArray;

var toArray = Belt_MutableQueue.toArray;

var make = Belt_MutableQueue.make;

var clear = Belt_MutableQueue.clear;

var add = Belt_MutableQueue.add;

var peek = Belt_MutableQueue.peek;

var pop = Belt_MutableQueue.pop;

var copy = Belt_MutableQueue.copy;

var size = Belt_MutableQueue.size;

var mapU = Belt_MutableQueue.mapU;

var map = Belt_MutableQueue.map;

var forEachU = Belt_MutableQueue.forEachU;

var forEach = Belt_MutableQueue.forEach;

var isEmpty = Belt_MutableQueue.isEmpty;

var reduceU = Belt_MutableQueue.reduceU;

var reduce = Belt_MutableQueue.reduce;

var transfer = Belt_MutableQueue.transfer;

export {
  fromArray ,
  toArray ,
  make ,
  clear ,
  add ,
  peek ,
  pop ,
  copy ,
  size ,
  mapU ,
  map ,
  forEachU ,
  forEach ,
  isEmpty ,
  reduceU ,
  reduce ,
  addMany ,
  transfer ,
  
}
/* No side effect */
