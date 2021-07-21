export var top = 'top';
export var bottom = 'bottom';
export var right = 'right';
export var left = 'left';
export var auto = 'auto';
export var basePlacements = [top, bottom, right, left];
export var start = 'start';
export var end = 'end';
export var clippingParents = 'clippingParents';
export var viewport = 'viewport';
export var popper = 'popper';
export var reference = 'reference';
export var variationPlacements = /*#__PURE__*/basePlacements.reduce(function (acc, placement) {
  return acc.concat([placement + "-" + start, placement + "-" + end]);
}, []);
export var placements = /*#__PURE__*/[].concat(basePlacements, [auto]).reduce(function (acc, placement) {
  return acc.concat([placement, placement + "-" + start, placement + "-" + end]);
}, []); // modifiers that need to read the DOM

export var beforeRead = 'beforeRead';
export var read = 'read';
export var afterRead = 'afterRead'; // pure-logic modifiers

export var beforeMain = 'beforeMain';
export var main = 'main';
export var afterMain = 'afterMain'; // modifier with the purpose to write to the DOM (or write into a framework state)

export var beforeWrite = 'beforeWrite';
export var write = 'write';
export var afterWrite = 'afterWrite';
export var modifierPhases = [beforeRead, read, afterRead, beforeMain, main, afterMain, beforeWrite, write, afterWrite];