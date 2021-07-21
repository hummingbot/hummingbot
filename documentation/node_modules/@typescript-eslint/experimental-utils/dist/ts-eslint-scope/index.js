"use strict";
function __export(m) {
    for (var p in m) if (!exports.hasOwnProperty(p)) exports[p] = m[p];
}
Object.defineProperty(exports, "__esModule", { value: true });
const eslint_scope_1 = require("eslint-scope");
__export(require("./analyze"));
__export(require("./Definition"));
__export(require("./PatternVisitor"));
__export(require("./Reference"));
__export(require("./Referencer"));
__export(require("./Scope"));
__export(require("./ScopeManager"));
__export(require("./Variable"));
exports.version = eslint_scope_1.version;
//# sourceMappingURL=index.js.map