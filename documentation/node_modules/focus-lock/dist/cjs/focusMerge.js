'use strict';

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.getFocusabledIn = exports.newFocus = exports.NEW_FOCUS = undefined;

var _DOMutils = require('./utils/DOMutils');

var _firstFocus = require('./utils/firstFocus');

var _firstFocus2 = _interopRequireDefault(_firstFocus);

var _allAffected = require('./utils/all-affected');

var _allAffected2 = _interopRequireDefault(_allAffected);

var _array = require('./utils/array');

var _correctFocus = require('./utils/correctFocus');

function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

var findAutoFocused = function findAutoFocused(autoFocusables) {
  return function (node) {
    return !!node.autofocus || node.dataset && !!node.dataset.autofocus || autoFocusables.indexOf(node) >= 0;
  };
};

var isGuard = function isGuard(node) {
  return node && node.dataset && node.dataset.focusGuard;
};
var notAGuard = function notAGuard(node) {
  return !isGuard(node);
};

var NEW_FOCUS = exports.NEW_FOCUS = 'NEW_FOCUS';

var newFocus = exports.newFocus = function newFocus(innerNodes, outerNodes, activeElement, lastNode) {
  var cnt = innerNodes.length;
  var firstFocus = innerNodes[0];
  var lastFocus = innerNodes[cnt - 1];
  var isOnGuard = isGuard(activeElement);

  // focus is inside
  if (innerNodes.indexOf(activeElement) >= 0) {
    return undefined;
  }

  var activeIndex = outerNodes.indexOf(activeElement);
  var lastIndex = outerNodes.indexOf(lastNode || activeIndex);
  var lastNodeInside = innerNodes.indexOf(lastNode);
  var indexDiff = activeIndex - lastIndex;
  var firstNodeIndex = outerNodes.indexOf(firstFocus);
  var lastNodeIndex = outerNodes.indexOf(lastFocus);

  var correctedNodes = (0, _correctFocus.correctNodes)(outerNodes);
  var correctedIndexDiff = correctedNodes.indexOf(activeElement) - correctedNodes.indexOf(lastNode || activeIndex);

  var returnFirstNode = (0, _firstFocus.pickFocusable)(innerNodes, 0);
  var returnLastNode = (0, _firstFocus.pickFocusable)(innerNodes, cnt - 1);

  // new focus
  if (activeIndex === -1 || lastNodeInside === -1) {
    return NEW_FOCUS;
  }
  // old focus
  if (!indexDiff && lastNodeInside >= 0) {
    return lastNodeInside;
  }
  // first element
  if (activeIndex <= firstNodeIndex && isOnGuard && Math.abs(indexDiff) > 1) {
    return returnLastNode;
  }
  // last element
  if (activeIndex >= lastNodeIndex && isOnGuard && Math.abs(indexDiff) > 1) {
    return returnFirstNode;
  }
  // jump out, but not on the guard
  if (indexDiff && Math.abs(correctedIndexDiff) > 1) {
    return lastNodeInside;
  }
  // focus above lock
  if (activeIndex <= firstNodeIndex) {
    return returnLastNode;
  }
  // focus below lock
  if (activeIndex > lastNodeIndex) {
    return returnFirstNode;
  }
  // index is inside tab order, but outside Lock
  if (indexDiff) {
    if (Math.abs(indexDiff) > 1) {
      return lastNodeInside;
    }
    return (cnt + lastNodeInside + indexDiff) % cnt;
  }
  // do nothing
  return undefined;
};

var getTopCommonParent = function getTopCommonParent(baseActiveElement, leftEntry, rightEntries) {
  var activeElements = (0, _array.asArray)(baseActiveElement);
  var leftEntries = (0, _array.asArray)(leftEntry);
  var activeElement = activeElements[0];
  var topCommon = null;
  leftEntries.filter(Boolean).forEach(function (entry) {
    topCommon = (0, _DOMutils.getCommonParent)(topCommon || entry, entry) || topCommon;
    rightEntries.filter(Boolean).forEach(function (subEntry) {
      var common = (0, _DOMutils.getCommonParent)(activeElement, subEntry);
      if (common) {
        if (!topCommon || common.contains(topCommon)) {
          topCommon = common;
        } else {
          topCommon = (0, _DOMutils.getCommonParent)(common, topCommon);
        }
      }
    });
  });
  return topCommon;
};

var allParentAutofocusables = function allParentAutofocusables(entries) {
  return entries.reduce(function (acc, node) {
    return acc.concat((0, _DOMutils.parentAutofocusables)(node));
  }, []);
};

var reorderNodes = function reorderNodes(srcNodes, dstNodes) {
  var remap = new Map();
  // no Set(dstNodes) for IE11 :(
  dstNodes.forEach(function (entity) {
    return remap.set(entity.node, entity);
  });
  // remap to dstNodes
  return srcNodes.map(function (node) {
    return remap.get(node);
  }).filter(Boolean);
};

var getFocusabledIn = exports.getFocusabledIn = function getFocusabledIn(topNode) {
  var entries = (0, _allAffected2.default)(topNode).filter(notAGuard);
  var commonParent = getTopCommonParent(topNode, topNode, entries);
  var outerNodes = (0, _DOMutils.getTabbableNodes)([commonParent], true);
  var innerElements = (0, _DOMutils.getTabbableNodes)(entries).filter(function (_ref) {
    var node = _ref.node;
    return notAGuard(node);
  }).map(function (_ref2) {
    var node = _ref2.node;
    return node;
  });

  return outerNodes.map(function (_ref3) {
    var node = _ref3.node,
        index = _ref3.index;
    return {
      node: node,
      index: index,
      lockItem: innerElements.indexOf(node) >= 0,
      guard: isGuard(node)
    };
  });
};

var getFocusMerge = function getFocusMerge(topNode, lastNode) {
  var activeElement = document && document.activeElement;
  var entries = (0, _allAffected2.default)(topNode).filter(notAGuard);

  var commonParent = getTopCommonParent(activeElement || topNode, topNode, entries);

  var anyFocusable = (0, _DOMutils.getAllTabbableNodes)(entries);
  var innerElements = (0, _DOMutils.getTabbableNodes)(entries).filter(function (_ref4) {
    var node = _ref4.node;
    return notAGuard(node);
  });

  if (!innerElements[0]) {
    innerElements = anyFocusable;
    if (!innerElements[0]) {
      return undefined;
    }
  }

  var outerNodes = (0, _DOMutils.getAllTabbableNodes)([commonParent]).map(function (_ref5) {
    var node = _ref5.node;
    return node;
  });
  var orderedInnerElements = reorderNodes(outerNodes, innerElements);
  var innerNodes = orderedInnerElements.map(function (_ref6) {
    var node = _ref6.node;
    return node;
  });

  var newId = newFocus(innerNodes, outerNodes, activeElement, lastNode);

  if (newId === "NEW_FOCUS") {
    var autoFocusable = anyFocusable.map(function (_ref7) {
      var node = _ref7.node;
      return node;
    }).filter(findAutoFocused(allParentAutofocusables(entries)));

    return {
      node: autoFocusable && autoFocusable.length ? (0, _firstFocus2.default)(autoFocusable) : (0, _firstFocus2.default)(innerNodes)
    };
  }

  if (newId === undefined) {
    return newId;
  }
  return orderedInnerElements[newId];
};

exports.default = getFocusMerge;