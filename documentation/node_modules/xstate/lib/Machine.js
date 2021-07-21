"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.createMachine = exports.Machine = void 0;
var StateNode_1 = require("./StateNode");
function Machine(config, options, initialContext) {
    if (initialContext === void 0) { initialContext = config.context; }
    var resolvedInitialContext = typeof initialContext === 'function'
        ? initialContext()
        : initialContext;
    return new StateNode_1.StateNode(config, options, resolvedInitialContext);
}
exports.Machine = Machine;
function createMachine(config, options) {
    var resolvedInitialContext = typeof config.context === 'function'
        ? config.context()
        : config.context;
    return new StateNode_1.StateNode(config, options, resolvedInitialContext);
}
exports.createMachine = createMachine;
