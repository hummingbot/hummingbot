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
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    Object.defineProperty(o, k2, { enumerable: true, get: function() { return m[k]; } });
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || function (mod) {
    if (mod && mod.__esModule) return mod;
    var result = {};
    if (mod != null) for (var k in mod) if (k !== "default" && Object.hasOwnProperty.call(mod, k)) __createBinding(result, mod, k);
    __setModuleDefault(result, mod);
    return result;
};
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
var selector_1 = __importDefault(require("./selector"));
var element_1 = __importDefault(require("./element"));
var ruleset_1 = __importDefault(require("./ruleset"));
var declaration_1 = __importDefault(require("./declaration"));
var detached_ruleset_1 = __importDefault(require("./detached-ruleset"));
var expression_1 = __importDefault(require("./expression"));
var contexts_1 = __importDefault(require("../contexts"));
var utils = __importStar(require("../utils"));
var Definition = /** @class */ (function (_super) {
    __extends(Definition, _super);
    function Definition(name, params, rules, condition, variadic, frames, visibilityInfo) {
        var _this = _super.call(this) || this;
        _this.name = name || 'anonymous mixin';
        _this.selectors = [new selector_1.default([new element_1.default(null, name, false, _this._index, _this._fileInfo)])];
        _this.params = params;
        _this.condition = condition;
        _this.variadic = variadic;
        _this.arity = params.length;
        _this.rules = rules;
        _this._lookups = {};
        var optionalParameters = [];
        _this.required = params.reduce(function (count, p) {
            if (!p.name || (p.name && !p.value)) {
                return count + 1;
            }
            else {
                optionalParameters.push(p.name);
                return count;
            }
        }, 0);
        _this.optionalParameters = optionalParameters;
        _this.frames = frames;
        _this.copyVisibilityInfo(visibilityInfo);
        _this.allowRoot = true;
        return _this;
    }
    Definition.prototype.accept = function (visitor) {
        if (this.params && this.params.length) {
            this.params = visitor.visitArray(this.params);
        }
        this.rules = visitor.visitArray(this.rules);
        if (this.condition) {
            this.condition = visitor.visit(this.condition);
        }
    };
    Definition.prototype.evalParams = function (context, mixinEnv, args, evaldArguments) {
        /* jshint boss:true */
        var frame = new ruleset_1.default(null, null);
        var varargs;
        var arg;
        var params = utils.copyArray(this.params);
        var i;
        var j;
        var val;
        var name;
        var isNamedFound;
        var argIndex;
        var argsLength = 0;
        if (mixinEnv.frames && mixinEnv.frames[0] && mixinEnv.frames[0].functionRegistry) {
            frame.functionRegistry = mixinEnv.frames[0].functionRegistry.inherit();
        }
        mixinEnv = new contexts_1.default.Eval(mixinEnv, [frame].concat(mixinEnv.frames));
        if (args) {
            args = utils.copyArray(args);
            argsLength = args.length;
            for (i = 0; i < argsLength; i++) {
                arg = args[i];
                if (name = (arg && arg.name)) {
                    isNamedFound = false;
                    for (j = 0; j < params.length; j++) {
                        if (!evaldArguments[j] && name === params[j].name) {
                            evaldArguments[j] = arg.value.eval(context);
                            frame.prependRule(new declaration_1.default(name, arg.value.eval(context)));
                            isNamedFound = true;
                            break;
                        }
                    }
                    if (isNamedFound) {
                        args.splice(i, 1);
                        i--;
                        continue;
                    }
                    else {
                        throw { type: 'Runtime', message: "Named argument for " + this.name + " " + args[i].name + " not found" };
                    }
                }
            }
        }
        argIndex = 0;
        for (i = 0; i < params.length; i++) {
            if (evaldArguments[i]) {
                continue;
            }
            arg = args && args[argIndex];
            if (name = params[i].name) {
                if (params[i].variadic) {
                    varargs = [];
                    for (j = argIndex; j < argsLength; j++) {
                        varargs.push(args[j].value.eval(context));
                    }
                    frame.prependRule(new declaration_1.default(name, new expression_1.default(varargs).eval(context)));
                }
                else {
                    val = arg && arg.value;
                    if (val) {
                        // This was a mixin call, pass in a detached ruleset of it's eval'd rules
                        if (Array.isArray(val)) {
                            val = new detached_ruleset_1.default(new ruleset_1.default('', val));
                        }
                        else {
                            val = val.eval(context);
                        }
                    }
                    else if (params[i].value) {
                        val = params[i].value.eval(mixinEnv);
                        frame.resetCache();
                    }
                    else {
                        throw { type: 'Runtime', message: "wrong number of arguments for " + this.name + " (" + argsLength + " for " + this.arity + ")" };
                    }
                    frame.prependRule(new declaration_1.default(name, val));
                    evaldArguments[i] = val;
                }
            }
            if (params[i].variadic && args) {
                for (j = argIndex; j < argsLength; j++) {
                    evaldArguments[j] = args[j].value.eval(context);
                }
            }
            argIndex++;
        }
        return frame;
    };
    Definition.prototype.makeImportant = function () {
        var rules = !this.rules ? this.rules : this.rules.map(function (r) {
            if (r.makeImportant) {
                return r.makeImportant(true);
            }
            else {
                return r;
            }
        });
        var result = new Definition(this.name, this.params, rules, this.condition, this.variadic, this.frames);
        return result;
    };
    Definition.prototype.eval = function (context) {
        return new Definition(this.name, this.params, this.rules, this.condition, this.variadic, this.frames || utils.copyArray(context.frames));
    };
    Definition.prototype.evalCall = function (context, args, important) {
        var _arguments = [];
        var mixinFrames = this.frames ? this.frames.concat(context.frames) : context.frames;
        var frame = this.evalParams(context, new contexts_1.default.Eval(context, mixinFrames), args, _arguments);
        var rules;
        var ruleset;
        frame.prependRule(new declaration_1.default('@arguments', new expression_1.default(_arguments).eval(context)));
        rules = utils.copyArray(this.rules);
        ruleset = new ruleset_1.default(null, rules);
        ruleset.originalRuleset = this;
        ruleset = ruleset.eval(new contexts_1.default.Eval(context, [this, frame].concat(mixinFrames)));
        if (important) {
            ruleset = ruleset.makeImportant();
        }
        return ruleset;
    };
    Definition.prototype.matchCondition = function (args, context) {
        if (this.condition && !this.condition.eval(new contexts_1.default.Eval(context, [this.evalParams(context, /* the parameter variables */ new contexts_1.default.Eval(context, this.frames ? this.frames.concat(context.frames) : context.frames), args, [])]
            .concat(this.frames || []) // the parent namespace/mixin frames
            .concat(context.frames)))) { // the current environment frames
            return false;
        }
        return true;
    };
    Definition.prototype.matchArgs = function (args, context) {
        var allArgsCnt = (args && args.length) || 0;
        var len;
        var optionalParameters = this.optionalParameters;
        var requiredArgsCnt = !args ? 0 : args.reduce(function (count, p) {
            if (optionalParameters.indexOf(p.name) < 0) {
                return count + 1;
            }
            else {
                return count;
            }
        }, 0);
        if (!this.variadic) {
            if (requiredArgsCnt < this.required) {
                return false;
            }
            if (allArgsCnt > this.params.length) {
                return false;
            }
        }
        else {
            if (requiredArgsCnt < (this.required - 1)) {
                return false;
            }
        }
        // check patterns
        len = Math.min(requiredArgsCnt, this.arity);
        for (var i = 0; i < len; i++) {
            if (!this.params[i].name && !this.params[i].variadic) {
                if (args[i].value.eval(context).toCSS() != this.params[i].value.eval(context).toCSS()) {
                    return false;
                }
            }
        }
        return true;
    };
    return Definition;
}(ruleset_1.default));
Definition.prototype.type = 'MixinDefinition';
Definition.prototype.evalFirst = true;
exports.default = Definition;
//# sourceMappingURL=mixin-definition.js.map