"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
var toArray = exports.toArray = function toArray(a) {
  var ret = Array(a.length);
  for (var i = 0; i < a.length; ++i) {
    ret[i] = a[i];
  }
  return ret;
};

var arrayFind = exports.arrayFind = function arrayFind(array, search) {
  return array.filter(function (a) {
    return a === search;
  })[0];
};

var asArray = exports.asArray = function asArray(a) {
  return Array.isArray(a) ? a : [a];
};