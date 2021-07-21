"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.each = void 0;
function each(collection, item, indexOrActions, maybeActions) {
    var actions = maybeActions || indexOrActions;
    var index = maybeActions ? indexOrActions : undefined;
    return {
        type: 'xstate.foreach',
        collection: collection,
        item: item,
        index: index,
        actions: actions
    };
}
exports.each = each;
