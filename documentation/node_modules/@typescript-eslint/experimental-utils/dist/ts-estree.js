"use strict";
// for convenience's sake - export the types directly from here so consumers
// don't need to reference/install both packages in their code
Object.defineProperty(exports, "__esModule", { value: true });
// NOTE - this uses hard links inside ts-estree to avoid initialization of entire package
//        via its main file (which imports typescript at runtime).
//        Not every eslint-plugin written in typescript requires typescript at runtime.
var ts_estree_1 = require("@typescript-eslint/typescript-estree/dist/ts-estree");
exports.AST_NODE_TYPES = ts_estree_1.AST_NODE_TYPES;
exports.AST_TOKEN_TYPES = ts_estree_1.AST_TOKEN_TYPES;
exports.TSESTree = ts_estree_1.TSESTree;
//# sourceMappingURL=ts-estree.js.map