type t('a) = array('a);

module Helpers = {
  [@bs.get_index] external get: (t('a), int) => option('a) = "";
};

[@bs.new] external make: unit => t('a) = "Array";
[@bs.set] external clear: (t('a), [@bs.as 0] _) => unit = "length";
[@bs.send] external push: (t('a), 'a) => unit = "push";
[@bs.send] external pop: t('a) => option('a) = "pop";
[@bs.send] external copy: t('a) => t('a) = "slice";
[@bs.get] external size: t('a) => int = "length";
[@bs.send] external forEachU: (t('a), (. 'a) => unit) => unit = "forEach";
[@bs.send] external forEach: (t('a), 'a => unit) => unit = "forEach";

let isEmpty = (stack: t('a)): bool => size(stack) === 0;

let top = (stack: t('a)): option('a) =>
  Helpers.get(stack, size(stack) - 1);
