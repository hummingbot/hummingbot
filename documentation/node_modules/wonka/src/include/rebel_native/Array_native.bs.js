

import * as $$Array from "bs-platform/lib/es6/array.js";
import * as Curry from "bs-platform/lib/es6/curry.js";
import * as Belt_Array from "bs-platform/lib/es6/belt_Array.js";
import * as Caml_option from "bs-platform/lib/es6/caml_option.js";

function makeEmpty(param) {
  return [];
}

function makeUninitialized(prim) {
  return new Array(prim);
}

function size(prim) {
  return prim.length;
}

function getUnsafe(prim, prim$1) {
  return prim[prim$1];
}

function setUnsafe(prim, prim$1, prim$2) {
  prim[prim$1] = prim$2;
  
}

function fill(arr, x) {
  return Belt_Array.fill(arr, 0, arr.length, x);
}

function copy(prim) {
  return prim.slice(0);
}

function slice(arr, start, end_) {
  var len = end_ - start | 0;
  return Belt_Array.slice(arr, start, len);
}

function append(arr, x) {
  return Belt_Array.concat(arr, [x]);
}

function somei(arr, f) {
  var len = arr.length;
  var _i = 0;
  while(true) {
    var i = _i;
    if (i >= len) {
      return false;
    }
    if (Curry._2(f, arr[i], i)) {
      return true;
    }
    _i = i + 1 | 0;
    continue ;
  };
}

function everyi(arr, f) {
  var len = arr.length;
  var _i = 0;
  while(true) {
    var i = _i;
    if (i >= len) {
      return true;
    }
    if (!Curry._2(f, arr[i], i)) {
      return false;
    }
    _i = i + 1 | 0;
    continue ;
  };
}

function findi(arr, f) {
  var len = arr.length;
  var _i = 0;
  while(true) {
    var i = _i;
    if (i >= len) {
      return ;
    }
    var x = arr[i];
    if (Curry._2(f, x, i)) {
      return Caml_option.some(x);
    }
    _i = i + 1 | 0;
    continue ;
  };
}

function findIndex(arr, f) {
  var len = arr.length;
  var _i = 0;
  while(true) {
    var i = _i;
    if (i >= len) {
      return -1;
    }
    if (Curry._1(f, arr[i])) {
      return i;
    }
    _i = i + 1 | 0;
    continue ;
  };
}

function lastIndexOf(arr, x) {
  var len = arr.length;
  var _i = len - 1 | 0;
  while(true) {
    var i = _i;
    if (i < 0) {
      return -1;
    }
    if (x === arr[i]) {
      return i;
    }
    _i = i - 1 | 0;
    continue ;
  };
}

function filteri(arr, f) {
  var len = arr.length;
  var res = arr.slice(0);
  var j = {
    contents: -1
  };
  var _i = 0;
  while(true) {
    var i = _i;
    if (i >= len) {
      return $$Array.sub(res, 0, j.contents + 1 | 0);
    }
    var x = arr[i];
    if (Curry._2(f, x, i)) {
      j.contents = j.contents + 1 | 0;
      arr[j.contents] = x;
    }
    _i = i + 1 | 0;
    continue ;
  };
}

function removeCount(arr, pos, count) {
  var len = arr.length;
  var pos2 = (pos + count | 0) - 1 | 0;
  var res = $$Array.sub(arr, 0, len - count | 0);
  var _i = 0;
  while(true) {
    var i = _i;
    if (i >= len) {
      return res;
    }
    if (i >= pos && i <= pos2) {
      _i = i + 1 | 0;
      continue ;
    }
    var j = i > pos2 ? i - count | 0 : i;
    arr[j] = arr[i];
    _i = i + 1 | 0;
    continue ;
  };
}

function find(arr, f) {
  return findi(arr, (function (x, _i) {
                return Curry._1(f, x);
              }));
}

function indexOf(arr, x) {
  return findIndex(arr, (function (item) {
                return item === x;
              }));
}

function includes(arr, x) {
  return findIndex(arr, (function (item) {
                return item === x;
              })) > -1;
}

function filter(arr, f) {
  return filteri(arr, (function (x, _i) {
                return Curry._1(f, x);
              }));
}

function remove(arr, index) {
  return removeCount(arr, index, 1);
}

function mapi(arr, f) {
  return Belt_Array.mapWithIndexU(arr, (function (i, x) {
                return Curry._2(f, x, i);
              }));
}

function forEachi(arr, f) {
  return Belt_Array.forEachWithIndexU(arr, (function (i, x) {
                return Curry._2(f, x, i);
              }));
}

function reduce(arr, reducer, acc) {
  return Belt_Array.reduce(arr, acc, reducer);
}

function reduceRight(arr, reducer, acc) {
  return Belt_Array.reduceReverse(arr, acc, reducer);
}

var make = Belt_Array.make;

var get = Belt_Array.get;

var set = Belt_Array.set;

var reverseInPlace = Belt_Array.reverseInPlace;

var reverse = Belt_Array.reverse;

var shuffle = Belt_Array.shuffle;

var shuffleInPlace = Belt_Array.shuffleInPlace;

var concat = Belt_Array.concat;

var some = Belt_Array.some;

var every = Belt_Array.every;

var map = Belt_Array.map;

var forEach = Belt_Array.forEach;

export {
  makeEmpty ,
  makeUninitialized ,
  make ,
  size ,
  get ,
  getUnsafe ,
  set ,
  setUnsafe ,
  fill ,
  reverseInPlace ,
  reverse ,
  shuffle ,
  shuffleInPlace ,
  copy ,
  slice ,
  concat ,
  append ,
  somei ,
  everyi ,
  findi ,
  findIndex ,
  lastIndexOf ,
  filteri ,
  removeCount ,
  find ,
  indexOf ,
  includes ,
  filter ,
  remove ,
  some ,
  every ,
  map ,
  mapi ,
  forEach ,
  forEachi ,
  reduce ,
  reduceRight ,
  
}
/* No side effect */
