"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
var SetTreeVisibilityVisitor = /** @class */ (function () {
    function SetTreeVisibilityVisitor(visible) {
        this.visible = visible;
    }
    SetTreeVisibilityVisitor.prototype.run = function (root) {
        this.visit(root);
    };
    SetTreeVisibilityVisitor.prototype.visitArray = function (nodes) {
        if (!nodes) {
            return nodes;
        }
        var cnt = nodes.length;
        var i;
        for (i = 0; i < cnt; i++) {
            this.visit(nodes[i]);
        }
        return nodes;
    };
    SetTreeVisibilityVisitor.prototype.visit = function (node) {
        if (!node) {
            return node;
        }
        if (node.constructor === Array) {
            return this.visitArray(node);
        }
        if (!node.blocksVisibility || node.blocksVisibility()) {
            return node;
        }
        if (this.visible) {
            node.ensureVisibility();
        }
        else {
            node.ensureInvisibility();
        }
        node.accept(this);
        return node;
    };
    return SetTreeVisibilityVisitor;
}());
exports.default = SetTreeVisibilityVisitor;
//# sourceMappingURL=set-tree-visibility-visitor.js.map