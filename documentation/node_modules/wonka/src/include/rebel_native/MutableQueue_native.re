type t('a) = Belt.MutableQueue.t('a);

let fromArray = Belt.MutableQueue.fromArray;
let toArray = Belt.MutableQueue.toArray;
let make = Belt.MutableQueue.make;
let clear = Belt.MutableQueue.clear;
let add = Belt.MutableQueue.add;
let peek = Belt.MutableQueue.peek;
let pop = Belt.MutableQueue.pop;
let copy = Belt.MutableQueue.copy;
let size = Belt.MutableQueue.size;
let mapU = Belt.MutableQueue.mapU;
let map = Belt.MutableQueue.map;
let forEachU = Belt.MutableQueue.forEachU;
let forEach = Belt.MutableQueue.forEach;

let isEmpty = Belt.MutableQueue.isEmpty;
let reduceU = Belt.MutableQueue.reduceU;
let reduce = Belt.MutableQueue.reduce;

let addMany = (q1: t('a), q2: t('a)) =>
  Belt.MutableQueue.transfer(copy(q1), q2);

let transfer = Belt.MutableQueue.transfer;
