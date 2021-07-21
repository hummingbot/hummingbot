"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
var contexts_1 = __importDefault(require("./contexts"));
var visitors_1 = __importDefault(require("./visitors"));
var tree_1 = __importDefault(require("./tree"));
exports.default = (function (root, options) {
    if (options === void 0) { options = {}; }
    var evaldRoot;
    var variables = options.variables;
    var evalEnv = new contexts_1.default.Eval(options);
    //
    // Allows setting variables with a hash, so:
    //
    //   `{ color: new tree.Color('#f01') }` will become:
    //
    //   new tree.Declaration('@color',
    //     new tree.Value([
    //       new tree.Expression([
    //         new tree.Color('#f01')
    //       ])
    //     ])
    //   )
    //
    if (typeof variables === 'object' && !Array.isArray(variables)) {
        variables = Object.keys(variables).map(function (k) {
            var value = variables[k];
            if (!(value instanceof tree_1.default.Value)) {
                if (!(value instanceof tree_1.default.Expression)) {
                    value = new tree_1.default.Expression([value]);
                }
                value = new tree_1.default.Value([value]);
            }
            return new tree_1.default.Declaration("@" + k, value, false, null, 0);
        });
        evalEnv.frames = [new tree_1.default.Ruleset(null, variables)];
    }
    var visitors = [
        new visitors_1.default.JoinSelectorVisitor(),
        new visitors_1.default.MarkVisibleSelectorsVisitor(true),
        new visitors_1.default.ExtendVisitor(),
        new visitors_1.default.ToCSSVisitor({ compress: Boolean(options.compress) })
    ];
    var preEvalVisitors = [];
    var v;
    var visitorIterator;
    /**
     * first() / get() allows visitors to be added while visiting
     *
     * @todo Add scoping for visitors just like functions for @plugin; right now they're global
     */
    if (options.pluginManager) {
        visitorIterator = options.pluginManager.visitor();
        for (var i = 0; i < 2; i++) {
            visitorIterator.first();
            while ((v = visitorIterator.get())) {
                if (v.isPreEvalVisitor) {
                    if (i === 0 || preEvalVisitors.indexOf(v) === -1) {
                        preEvalVisitors.push(v);
                        v.run(root);
                    }
                }
                else {
                    if (i === 0 || visitors.indexOf(v) === -1) {
                        if (v.isPreVisitor) {
                            visitors.unshift(v);
                        }
                        else {
                            visitors.push(v);
                        }
                    }
                }
            }
        }
    }
    evaldRoot = root.eval(evalEnv);
    for (var i = 0; i < visitors.length; i++) {
        visitors[i].run(evaldRoot);
    }
    // Run any remaining visitors added after eval pass
    if (options.pluginManager) {
        visitorIterator.first();
        while ((v = visitorIterator.get())) {
            if (visitors.indexOf(v) === -1 && preEvalVisitors.indexOf(v) === -1) {
                v.run(evaldRoot);
            }
        }
    }
    return evaldRoot;
});
//# sourceMappingURL=transform-tree.js.map