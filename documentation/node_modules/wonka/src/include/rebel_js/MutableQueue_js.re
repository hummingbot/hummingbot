type t('a) = array('a);

external fromArray: array('a) => t('a) = "%identity";
external toArray: t('a) => array('a) = "%identity";
[@bs.new] external make: unit => t('a) = "Array";
[@bs.set] external clear: (t('a), [@bs.as 0] _) => unit = "length";
[@bs.send] external add: (t('a), 'a) => unit = "push";
[@bs.get] external peek: t('a) => option('a) = "0";
[@bs.send] external pop: t('a) => option('a) = "shift";
[@bs.send] external copy: t('a) => t('a) = "slice";
[@bs.get] external size: t('a) => int = "length";
[@bs.send] external mapU: (t('a), (. 'a) => 'b) => t('b) = "map";
[@bs.send] external map: (t('a), 'a => 'b) => t('b) = "map";
[@bs.send] external forEachU: (t('a), (. 'a) => unit) => unit = "forEach";
[@bs.send] external forEach: (t('a), 'a => unit) => unit = "forEach";

let isEmpty = (q: t('a)): bool => size(q) === 0;

let reduceU = (q: t('a), accu: 'b, f: (. 'b, 'a) => 'b): 'b =>
  Js.Array.reduce((acc, x) => f(. acc, x), accu, q);

let reduce = (q: t('a), accu: 'b, f: ('b, 'a) => 'b): 'b =>
  Js.Array.reduce(f, accu, q);

[@bs.scope ("Array", "prototype", "push")] [@bs.val]
external addMany: (t('a), t('a)) => unit = "apply";

let transfer = (q1: t('a), q2: t('a)) => {
  addMany(q1, q2);
  clear(q1);
};
