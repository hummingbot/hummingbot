"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
var visitor_1 = __importDefault(require("./visitor"));
var JoinSelectorVisitor = /** @class */ (function () {
    function JoinSelectorVisitor() {
        this.contexts = [[]];
        this._visitor = new visitor_1.default(this);
    }
    JoinSelectorVisitor.prototype.run = function (root) {
        return this._visitor.visit(root);
    };
    JoinSelectorVisitor.prototype.visitDeclaration = function (declNode, visitArgs) {
        visitArgs.visitDeeper = false;
    };
    JoinSelectorVisitor.prototype.visitMixinDefinition = function (mixinDefinitionNode, visitArgs) {
        visitArgs.visitDeeper = false;
    };
    JoinSelectorVisitor.prototype.visitRuleset = function (rulesetNode, visitArgs) {
        var context = this.contexts[this.contexts.length - 1];
        var paths = [];
        var selectors;
        this.contexts.push(paths);
        if (!rulesetNode.root) {
            selectors = rulesetNode.selectors;
            if (selectors) {
                selectors = selectors.filter(function (selector) { return selector.getIsOutput(); });
                rulesetNode.selectors = selectors.length ? selectors : (selectors = null);
                if (selectors) {
                    rulesetNode.joinSelectors(paths, context, selectors);
                }
            }
            if (!selectors) {
                rulesetNode.rules = null;
            }
            rulesetNode.paths = paths;
        }
    };
    JoinSelectorVisitor.prototype.visitRulesetOut = function (rulesetNode) {
        this.contexts.length = this.contexts.length - 1;
    };
    JoinSelectorVisitor.prototype.visitMedia = function (mediaNode, visitArgs) {
        var context = this.contexts[this.contexts.length - 1];
        mediaNode.rules[0].root = (context.length === 0 || context[0].multiMedia);
    };
    JoinSelectorVisitor.prototype.visitAtRule = function (atRuleNode, visitArgs) {
        var context = this.contexts[this.contexts.length - 1];
        if (atRuleNode.rules && atRuleNode.rules.length) {
            atRuleNode.rules[0].root = (atRuleNode.isRooted || context.length === 0 || null);
        }
    };
    return JoinSelectorVisitor;
}());
exports.default = JoinSelectorVisitor;
//# sourceMappingURL=join-selector-visitor.js.map