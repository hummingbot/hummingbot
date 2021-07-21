"use strict";
var __importStar = (this && this.__importStar) || function (mod) {
    if (mod && mod.__esModule) return mod;
    var result = {};
    if (mod != null) for (var k in mod) if (Object.hasOwnProperty.call(mod, k)) result[k] = mod[k];
    result["default"] = mod;
    return result;
};
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const ts = __importStar(require("typescript"));
const dot_notation_1 = __importDefault(require("eslint/lib/rules/dot-notation"));
const util_1 = require("../util");
exports.default = util_1.createRule({
    name: 'dot-notation',
    meta: {
        type: 'suggestion',
        docs: {
            description: 'enforce dot notation whenever possible',
            category: 'Best Practices',
            recommended: false,
            extendsBaseRule: true,
            requiresTypeChecking: true,
        },
        schema: [
            {
                type: 'object',
                properties: {
                    allowKeywords: {
                        type: 'boolean',
                        default: true,
                    },
                    allowPattern: {
                        type: 'string',
                        default: '',
                    },
                    allowPrivateClassPropertyAccess: {
                        tyoe: 'boolean',
                        default: false,
                    },
                },
                additionalProperties: false,
            },
        ],
        fixable: dot_notation_1.default.meta.fixable,
        messages: dot_notation_1.default.meta.messages,
    },
    defaultOptions: [
        {
            allowPrivateClassPropertyAccess: false,
            allowKeywords: true,
            allowPattern: '',
        },
    ],
    create(context, [options]) {
        const rules = dot_notation_1.default.create(context);
        const allowPrivateClassPropertyAccess = options.allowPrivateClassPropertyAccess;
        const parserServices = util_1.getParserServices(context);
        const typeChecker = parserServices.program.getTypeChecker();
        return {
            MemberExpression(node) {
                var _a, _b, _c;
                if (allowPrivateClassPropertyAccess && node.computed) {
                    // for perf reasons - only fetch the symbol if we have to
                    const objectSymbol = typeChecker.getSymbolAtLocation(parserServices.esTreeNodeToTSNodeMap.get(node.property));
                    if (((_c = (_b = (_a = objectSymbol === null || objectSymbol === void 0 ? void 0 : objectSymbol.getDeclarations()) === null || _a === void 0 ? void 0 : _a[0]) === null || _b === void 0 ? void 0 : _b.modifiers) === null || _c === void 0 ? void 0 : _c[0].kind) ===
                        ts.SyntaxKind.PrivateKeyword) {
                        return;
                    }
                }
                rules.MemberExpression(node);
            },
        };
    },
});
//# sourceMappingURL=dot-notation.js.map