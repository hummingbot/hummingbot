"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.isASubscriptionOperation = void 0;
var graphql_1 = require("graphql");
exports.isASubscriptionOperation = function (document, operationName) {
    var operationAST = graphql_1.getOperationAST(document, operationName);
    return !!operationAST && operationAST.operation === 'subscription';
};
//# sourceMappingURL=is-subscriptions.js.map