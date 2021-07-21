type t('a) = array('a);

[@bs.new] external makeEmpty: unit => t('a) = "Array";
[@bs.new] external makeUninitialized: int => t('a) = "Array";

[@bs.get] external size: t('a) => int = "length";
[@bs.get_index] external get: (t('a), int) => option('a) = "";
[@bs.get_index] external getUnsafe: (t('a), int) => 'a = "";
[@bs.set_index] external setUnsafe: (t('a), int, 'a) => unit = "";

[@bs.send] external fill: (t('a), 'a) => unit = "fill";
[@bs.send] external reverseInPlace: t('a) => unit = "reverse";

[@bs.send] external copy: t('a) => t('a) = "slice";
[@bs.send]
external slice: (t('a), ~start: int, ~end_: int) => t('a) = "slice";
[@bs.send] external append: (t('a), 'a) => t('a) = "concat";
[@bs.send] external concat: (t('a), t('a)) => t('a) = "concat";

[@bs.send] external map: (t('a), 'a => 'b) => t('b) = "map";
[@bs.send] external mapi: (t('a), ('a, int) => 'b) => t('b) = "map";
[@bs.send] external some: (t('a), 'a => bool) => bool = "some";
[@bs.send] external somei: (t('a), ('a, int) => bool) => bool = "some";
[@bs.send] external every: (t('a), 'a => bool) => bool = "every";
[@bs.send] external everyi: (t('a), ('a, int) => bool) => bool = "every";
[@bs.send] external filter: (t('a), 'a => bool) => t('a) = "filter";
[@bs.send] external filteri: (t('a), ('a, int) => bool) => t('a) = "filter";
[@bs.send] external find: (t('a), 'a => bool) => option('a) = "find";
[@bs.send] external findi: (t('a), ('a, int) => bool) => option('a) = "find";
[@bs.send] external findIndex: (t('a), 'a => bool) => int = "findIndex";
[@bs.send] external forEach: (t('a), 'a => unit) => unit = "forEach";
[@bs.send] external forEachi: (t('a), ('a, int) => unit) => unit = "forEach";
[@bs.send] external reduce: (t('a), ('b, 'a) => 'b, 'b) => 'b = "reduce";
[@bs.send]
external reduceRight: (t('a), ('b, 'a) => 'b, 'b) => 'b = "reduceRight";

[@bs.send] external indexOf: (t('a), 'a) => int = "indexOf";
[@bs.send] external lastIndexOf: (t('a), 'a) => int = "lastIndexOf";

/* No need to replicate what Belt already has */
let shuffle = Belt.Array.shuffle;
let shuffleInPlace = Belt.Array.shuffleInPlace;

let make = (len: int, vals: 'a): t('a) => {
  let res = makeUninitialized(len);
  fill(res, vals);
  res;
};

let set = (arr: t('a), index: int, x: 'a) =>
  if (index < size(arr) && index >= 0) {
    setUnsafe(arr, index, x);
    true;
  } else {
    false;
  };

let reverse = (arr: t('a)): t('a) => {
  let res = copy(arr);
  reverseInPlace(arr);
  res;
};

let includes = (arr: t('a), x: 'a): bool => indexOf(arr, x) > (-1);

[@bs.send] external removeInPlace: (t('a), int) => t('a) = "splice";
[@bs.send]
external removeCountInPlace: (t('a), ~pos: int, ~count: int) => t('a) =
  "splice";

let remove = (arr: t('a), pos: int) => removeInPlace(copy(arr), pos);

let removeCount = (arr: t('a), ~pos: int, ~count: int) =>
  removeCountInPlace(copy(arr), ~pos, ~count);

module Js = {
  [@bs.send] external push: (t('a), 'a) => unit = "push";
  [@bs.send] external pop: t('a) => option('a) = "pop";
  [@bs.send] external unshift: (t('a), 'a) => unit = "unshift";
  [@bs.send] external shift: t('a) => option('a) = "shift";

  [@bs.scope ("Array", "prototype", "push")] [@bs.val]
  external pushMany: (t('a), t('a)) => unit = "apply";
  [@bs.scope ("Array", "prototype", "unshift")] [@bs.val]
  external unshiftMany: (t('a), t('a)) => unit = "apply";

  [@bs.send]
  external spliceInPlace:
    (t('a), ~pos: int, ~remove: int, ~add: t('a)) => t('a) =
    "splice";

  let splice = (arr: t('a), ~pos: int, ~remove: int, ~add: t('a)) =>
    spliceInPlace(copy(arr), ~pos, ~remove, ~add);
};
