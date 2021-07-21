"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
var comment_1 = __importDefault(require("../tree/comment"));
var dimension_1 = __importDefault(require("../tree/dimension"));
var declaration_1 = __importDefault(require("../tree/declaration"));
var expression_1 = __importDefault(require("../tree/expression"));
var ruleset_1 = __importDefault(require("../tree/ruleset"));
var selector_1 = __importDefault(require("../tree/selector"));
var element_1 = __importDefault(require("../tree/element"));
var quoted_1 = __importDefault(require("../tree/quoted"));
var getItemsFromNode = function (node) {
    // handle non-array values as an array of length 1
    // return 'undefined' if index is invalid
    var items = Array.isArray(node.value) ?
        node.value : Array(node);
    return items;
};
exports.default = {
    _SELF: function (n) {
        return n;
    },
    extract: function (values, index) {
        // (1-based index)
        index = index.value - 1;
        return getItemsFromNode(values)[index];
    },
    length: function (values) {
        return new dimension_1.default(getItemsFromNode(values).length);
    },
    /**
     * Creates a Less list of incremental values.
     * Modeled after Lodash's range function, also exists natively in PHP
     *
     * @param {Dimension} [start=1]
     * @param {Dimension} end  - e.g. 10 or 10px - unit is added to output
     * @param {Dimension} [step=1]
     */
    range: function (start, end, step) {
        var from;
        var to;
        var stepValue = 1;
        var list = [];
        if (end) {
            to = end;
            from = start.value;
            if (step) {
                stepValue = step.value;
            }
        }
        else {
            from = 1;
            to = start;
        }
        for (var i = from; i <= to.value; i += stepValue) {
            list.push(new dimension_1.default(i, to.unit));
        }
        return new expression_1.default(list);
    },
    each: function (list, rs) {
        var rules = [];
        var newRules;
        var iterator;
        if (list.value && !(list instanceof quoted_1.default)) {
            if (Array.isArray(list.value)) {
                iterator = list.value;
            }
            else {
                iterator = [list.value];
            }
        }
        else if (list.ruleset) {
            iterator = list.ruleset.rules;
        }
        else if (list.rules) {
            iterator = list.rules;
        }
        else if (Array.isArray(list)) {
            iterator = list;
        }
        else {
            iterator = [list];
        }
        var valueName = '@value';
        var keyName = '@key';
        var indexName = '@index';
        if (rs.params) {
            valueName = rs.params[0] && rs.params[0].name;
            keyName = rs.params[1] && rs.params[1].name;
            indexName = rs.params[2] && rs.params[2].name;
            rs = rs.rules;
        }
        else {
            rs = rs.ruleset;
        }
        for (var i = 0; i < iterator.length; i++) {
            var key = void 0;
            var value = void 0;
            var item = iterator[i];
            if (item instanceof declaration_1.default) {
                key = typeof item.name === 'string' ? item.name : item.name[0].value;
                value = item.value;
            }
            else {
                key = new dimension_1.default(i + 1);
                value = item;
            }
            if (item instanceof comment_1.default) {
                continue;
            }
            newRules = rs.rules.slice(0);
            if (valueName) {
                newRules.push(new declaration_1.default(valueName, value, false, false, this.index, this.currentFileInfo));
            }
            if (indexName) {
                newRules.push(new declaration_1.default(indexName, new dimension_1.default(i + 1), false, false, this.index, this.currentFileInfo));
            }
            if (keyName) {
                newRules.push(new declaration_1.default(keyName, key, false, false, this.index, this.currentFileInfo));
            }
            rules.push(new ruleset_1.default([new (selector_1.default)([new element_1.default("", '&')])], newRules, rs.strictImports, rs.visibilityInfo()));
        }
        return new ruleset_1.default([new (selector_1.default)([new element_1.default("", '&')])], rules, rs.strictImports, rs.visibilityInfo()).eval(this.context);
    }
};
//# sourceMappingURL=list.js.map