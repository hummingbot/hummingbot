"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
var visitor_1 = __importDefault(require("./visitor"));
var import_visitor_1 = __importDefault(require("./import-visitor"));
var set_tree_visibility_visitor_1 = __importDefault(require("./set-tree-visibility-visitor"));
var extend_visitor_1 = __importDefault(require("./extend-visitor"));
var join_selector_visitor_1 = __importDefault(require("./join-selector-visitor"));
var to_css_visitor_1 = __importDefault(require("./to-css-visitor"));
exports.default = {
    Visitor: visitor_1.default,
    ImportVisitor: import_visitor_1.default,
    MarkVisibleSelectorsVisitor: set_tree_visibility_visitor_1.default,
    ExtendVisitor: extend_visitor_1.default,
    JoinSelectorVisitor: join_selector_visitor_1.default,
    ToCSSVisitor: to_css_visitor_1.default
};
//# sourceMappingURL=index.js.map