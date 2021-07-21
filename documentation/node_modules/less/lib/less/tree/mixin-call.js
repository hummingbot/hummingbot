"use strict";
var __extends = (this && this.__extends) || (function () {
    var extendStatics = function (d, b) {
        extendStatics = Object.setPrototypeOf ||
            ({ __proto__: [] } instanceof Array && function (d, b) { d.__proto__ = b; }) ||
            function (d, b) { for (var p in b) if (b.hasOwnProperty(p)) d[p] = b[p]; };
        return extendStatics(d, b);
    };
    return function (d, b) {
        extendStatics(d, b);
        function __() { this.constructor = d; }
        d.prototype = b === null ? Object.create(b) : (__.prototype = b.prototype, new __());
    };
})();
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
var node_1 = __importDefault(require("./node"));
var selector_1 = __importDefault(require("./selector"));
var mixin_definition_1 = __importDefault(require("./mixin-definition"));
var default_1 = __importDefault(require("../functions/default"));
var MixinCall = /** @class */ (function (_super) {
    __extends(MixinCall, _super);
    function MixinCall(elements, args, index, currentFileInfo, important) {
        var _this = _super.call(this) || this;
        _this.selector = new selector_1.default(elements);
        _this.arguments = args || [];
        _this._index = index;
        _this._fileInfo = currentFileInfo;
        _this.important = important;
        _this.allowRoot = true;
        _this.setParent(_this.selector, _this);
        return _this;
    }
    MixinCall.prototype.accept = function (visitor) {
        if (this.selector) {
            this.selector = visitor.visit(this.selector);
        }
        if (this.arguments.length) {
            this.arguments = visitor.visitArray(this.arguments);
        }
    };
    MixinCall.prototype.eval = function (context) {
        var mixins;
        var mixin;
        var mixinPath;
        var args = [];
        var arg;
        var argValue;
        var rules = [];
        var match = false;
        var i;
        var m;
        var f;
        var isRecursive;
        var isOneFound;
        var candidates = [];
        var candidate;
        var conditionResult = [];
        var defaultResult;
        var defFalseEitherCase = -1;
        var defNone = 0;
        var defTrue = 1;
        var defFalse = 2;
        var count;
        var originalRuleset;
        var noArgumentsFilter;
        this.selector = this.selector.eval(context);
        function calcDefGroup(mixin, mixinPath) {
            var f;
            var p;
            var namespace;
            for (f = 0; f < 2; f++) {
                conditionResult[f] = true;
                default_1.default.value(f);
                for (p = 0; p < mixinPath.length && conditionResult[f]; p++) {
                    namespace = mixinPath[p];
                    if (namespace.matchCondition) {
                        conditionResult[f] = conditionResult[f] && namespace.matchCondition(null, context);
                    }
                }
                if (mixin.matchCondition) {
                    conditionResult[f] = conditionResult[f] && mixin.matchCondition(args, context);
                }
            }
            if (conditionResult[0] || conditionResult[1]) {
                if (conditionResult[0] != conditionResult[1]) {
                    return conditionResult[1] ?
                        defTrue : defFalse;
                }
                return defNone;
            }
            return defFalseEitherCase;
        }
        for (i = 0; i < this.arguments.length; i++) {
            arg = this.arguments[i];
            argValue = arg.value.eval(context);
            if (arg.expand && Array.isArray(argValue.value)) {
                argValue = argValue.value;
                for (m = 0; m < argValue.length; m++) {
                    args.push({ value: argValue[m] });
                }
            }
            else {
                args.push({ name: arg.name, value: argValue });
            }
        }
        noArgumentsFilter = function (rule) { return rule.matchArgs(null, context); };
        for (i = 0; i < context.frames.length; i++) {
            if ((mixins = context.frames[i].find(this.selector, null, noArgumentsFilter)).length > 0) {
                isOneFound = true;
                // To make `default()` function independent of definition order we have two "subpasses" here.
                // At first we evaluate each guard *twice* (with `default() == true` and `default() == false`),
                // and build candidate list with corresponding flags. Then, when we know all possible matches,
                // we make a final decision.
                for (m = 0; m < mixins.length; m++) {
                    mixin = mixins[m].rule;
                    mixinPath = mixins[m].path;
                    isRecursive = false;
                    for (f = 0; f < context.frames.length; f++) {
                        if ((!(mixin instanceof mixin_definition_1.default)) && mixin === (context.frames[f].originalRuleset || context.frames[f])) {
                            isRecursive = true;
                            break;
                        }
                    }
                    if (isRecursive) {
                        continue;
                    }
                    if (mixin.matchArgs(args, context)) {
                        candidate = { mixin: mixin, group: calcDefGroup(mixin, mixinPath) };
                        if (candidate.group !== defFalseEitherCase) {
                            candidates.push(candidate);
                        }
                        match = true;
                    }
                }
                default_1.default.reset();
                count = [0, 0, 0];
                for (m = 0; m < candidates.length; m++) {
                    count[candidates[m].group]++;
                }
                if (count[defNone] > 0) {
                    defaultResult = defFalse;
                }
                else {
                    defaultResult = defTrue;
                    if ((count[defTrue] + count[defFalse]) > 1) {
                        throw { type: 'Runtime', message: "Ambiguous use of `default()` found when matching for `" + this.format(args) + "`", index: this.getIndex(), filename: this.fileInfo().filename };
                    }
                }
                for (m = 0; m < candidates.length; m++) {
                    candidate = candidates[m].group;
                    if ((candidate === defNone) || (candidate === defaultResult)) {
                        try {
                            mixin = candidates[m].mixin;
                            if (!(mixin instanceof mixin_definition_1.default)) {
                                originalRuleset = mixin.originalRuleset || mixin;
                                mixin = new mixin_definition_1.default('', [], mixin.rules, null, false, null, originalRuleset.visibilityInfo());
                                mixin.originalRuleset = originalRuleset;
                            }
                            var newRules = mixin.evalCall(context, args, this.important).rules;
                            this._setVisibilityToReplacement(newRules);
                            Array.prototype.push.apply(rules, newRules);
                        }
                        catch (e) {
                            throw { message: e.message, index: this.getIndex(), filename: this.fileInfo().filename, stack: e.stack };
                        }
                    }
                }
                if (match) {
                    return rules;
                }
            }
        }
        if (isOneFound) {
            throw { type: 'Runtime', message: "No matching definition was found for `" + this.format(args) + "`", index: this.getIndex(), filename: this.fileInfo().filename };
        }
        else {
            throw { type: 'Name', message: this.selector.toCSS().trim() + " is undefined", index: this.getIndex(), filename: this.fileInfo().filename };
        }
    };
    MixinCall.prototype._setVisibilityToReplacement = function (replacement) {
        var i;
        var rule;
        if (this.blocksVisibility()) {
            for (i = 0; i < replacement.length; i++) {
                rule = replacement[i];
                rule.addVisibilityBlock();
            }
        }
    };
    MixinCall.prototype.format = function (args) {
        return this.selector.toCSS().trim() + "(" + (args ? args.map(function (a) {
            var argValue = '';
            if (a.name) {
                argValue += a.name + ":";
            }
            if (a.value.toCSS) {
                argValue += a.value.toCSS();
            }
            else {
                argValue += '???';
            }
            return argValue;
        }).join(', ') : '') + ")";
    };
    return MixinCall;
}(node_1.default));
MixinCall.prototype.type = 'MixinCall';
exports.default = MixinCall;
//# sourceMappingURL=mixin-call.js.map