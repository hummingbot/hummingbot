type t('a) = Belt.MutableStack.t('a);

let make = Belt.MutableStack.make;
let clear = Belt.MutableStack.clear;
let push = Belt.MutableStack.push;
let pop = Belt.MutableStack.pop;
let copy = Belt.MutableStack.copy;
let size = Belt.MutableStack.size;
let forEachU = Belt.MutableStack.forEachU;
let forEach = Belt.MutableStack.forEach;

let isEmpty = Belt.MutableStack.isEmpty;
let top = Belt.MutableStack.top;
