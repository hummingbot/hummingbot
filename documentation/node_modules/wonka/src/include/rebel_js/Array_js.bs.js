

import * as Belt_Array from "bs-platform/lib/es6/belt_Array.js";

function make(len, vals) {
  var res = new Array(len);
  res.fill(vals);
  return res;
}

function set(arr, index, x) {
  if (index < arr.length && index >= 0) {
    arr[index] = x;
    return true;
  } else {
    return false;
  }
}

function reverse(arr) {
  var res = arr.slice();
  arr.reverse();
  return res;
}

function includes(arr, x) {
  return arr.indexOf(x) > -1;
}

function remove(arr, pos) {
  return arr.slice().splice(pos);
}

function removeCount(arr, pos, count) {
  return arr.slice().splice(pos, count);
}

function splice(arr, pos, remove, add) {
  return arr.slice().splice(pos, remove, add);
}

var Js = {
  splice: splice
};

var shuffle = Belt_Array.shuffle;

var shuffleInPlace = Belt_Array.shuffleInPlace;

export {
  shuffle ,
  shuffleInPlace ,
  make ,
  set ,
  reverse ,
  includes ,
  remove ,
  removeCount ,
  Js ,
  
}
/* No side effect */
