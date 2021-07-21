type t('a) = array('a);

let makeEmpty = (): t('a) => [||];
let makeUninitialized = Belt.Array.makeUninitializedUnsafe;
let make = Belt.Array.make;

let size = Belt.Array.size;
let get = Belt.Array.get;
let getUnsafe = Belt.Array.getUnsafe;
let set = Belt.Array.set;
let setUnsafe = Belt.Array.setUnsafe;

let fill = (arr: t('a), x: 'a) =>
  Belt.Array.fill(arr, ~offset=0, ~len=size(arr), x);

let reverseInPlace = Belt.Array.reverseInPlace;
let reverse = Belt.Array.reverse;
let shuffle = Belt.Array.shuffle;
let shuffleInPlace = Belt.Array.shuffleInPlace;

let copy = Belt.Array.copy;

let slice = (arr: t('a), ~start: int, ~end_: int): t('a) => {
  let len = end_ - start;
  Belt.Array.slice(arr, ~offset=start, ~len);
};

let concat = Belt.Array.concat;

let append = (arr: t('a), x: 'a) => Belt.Array.concat(arr, [|x|]);

let somei = (arr: t('a), f: ('a, int) => bool): bool => {
  let len = size(arr);
  let rec search = (i: int) =>
    if (i >= len) {
      false;
    } else if (f(getUnsafe(arr, i), i)) {
      true;
    } else {
      search(i + 1);
    };

  search(0);
};

let everyi = (arr: t('a), f: ('a, int) => bool): bool => {
  let len = size(arr);
  let rec search = (i: int) =>
    if (i >= len) {
      true;
    } else if (!f(getUnsafe(arr, i), i)) {
      false;
    } else {
      search(i + 1);
    };

  search(0);
};

let findi = (arr: t('a), f: ('a, int) => bool): option('a) => {
  let len = size(arr);
  let rec search = (i: int) =>
    if (i >= len) {
      None;
    } else {
      let x = getUnsafe(arr, i);
      if (f(x, i)) {
        Some(x);
      } else {
        search(i + 1);
      };
    };

  search(0);
};

let findIndex = (arr: t('a), f: 'a => bool): int => {
  let len = size(arr);
  let rec search = (i: int) =>
    if (i >= len) {
      (-1);
    } else if (f(getUnsafe(arr, i))) {
      i;
    } else {
      search(i + 1);
    };

  search(0);
};

let lastIndexOf = (arr: t('a), x: 'a): int => {
  let len = size(arr);
  let rec search = (i: int) =>
    if (i < 0) {
      (-1);
    } else if (x === getUnsafe(arr, i)) {
      i;
    } else {
      search(i - 1);
    };

  search(len - 1);
};

let filteri = (arr: t('a), f: ('a, int) => bool): t('a) => {
  let len = size(arr);
  let res: t('a) = copy(arr);
  let j = ref(-1);

  let rec filter = (i: int) =>
    if (i >= len) {
      Array.sub(res, 0, j^ + 1);
    } else {
      let x = getUnsafe(arr, i);
      if (f(x, i)) {
        j := j^ + 1;
        Belt.Array.setUnsafe(arr, j^, x);
      };

      filter(i + 1);
    };

  filter(0);
};

let removeCount = (arr: t('a), ~pos: int, ~count: int): t('a) => {
  let len = size(arr);
  let pos2 = pos + count - 1;
  let res = Array.sub(arr, 0, len - count);

  let rec copy = (i: int) =>
    if (i >= len) {
      res;
    } else if (i >= pos && i <= pos2) {
      copy(i + 1);
    } else {
      let j = i > pos2 ? i - count : i;
      Belt.Array.setUnsafe(arr, j, Belt.Array.getUnsafe(arr, i));
      copy(i + 1);
    };

  copy(0);
};

let find = (arr: t('a), f: 'a => bool): option('a) =>
  findi(arr, (x, _i) => f(x));
let indexOf = (arr: t('a), x: 'a): int => findIndex(arr, item => item === x);
let includes = (arr: t('a), x: 'a): bool =>
  findIndex(arr, item => item === x) > (-1);
let filter = (arr: t('a), f: 'a => bool): t('a) =>
  filteri(arr, (x, _i) => f(x));
let remove = (arr: t('a), index: int): t('a) =>
  removeCount(arr, ~pos=index, ~count=1);

let some = Belt.Array.some;
let every = Belt.Array.every;
let map = Belt.Array.map;
let mapi = (arr: t('a), f: ('a, int) => 'b): t('b) =>
  Belt.Array.mapWithIndexU(arr, (. i, x) => f(x, i));
let forEach = Belt.Array.forEach;
let forEachi = (arr: t('a), f: ('a, int) => unit): unit =>
  Belt.Array.forEachWithIndexU(arr, (. i, x) => f(x, i));
let reduce = (arr: t('a), reducer: ('b, 'a) => 'b, acc: 'b): 'b =>
  Belt.Array.reduce(arr, acc, reducer);
let reduceRight = (arr: t('a), reducer: ('b, 'a) => 'b, acc: 'b): 'b =>
  Belt.Array.reduceReverse(arr, acc, reducer);
