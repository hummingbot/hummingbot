"use strict";
var __assign = (this && this.__assign) || function () {
    __assign = Object.assign || function(t) {
        for (var s, i = 1, n = arguments.length; i < n; i++) {
            s = arguments[i];
            for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p))
                t[p] = s[p];
        }
        return t;
    };
    return __assign.apply(this, arguments);
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.parseLegacyProtocolMessage = void 0;
var message_types_1 = require("../message-types");
exports.parseLegacyProtocolMessage = function (connectionContext, message) {
    var messageToReturn = message;
    switch (message.type) {
        case message_types_1.default.INIT:
            connectionContext.isLegacy = true;
            messageToReturn = __assign(__assign({}, message), { type: message_types_1.default.GQL_CONNECTION_INIT });
            break;
        case message_types_1.default.SUBSCRIPTION_START:
            messageToReturn = {
                id: message.id,
                type: message_types_1.default.GQL_START,
                payload: {
                    query: message.query,
                    operationName: message.operationName,
                    variables: message.variables,
                },
            };
            break;
        case message_types_1.default.SUBSCRIPTION_END:
            messageToReturn = __assign(__assign({}, message), { type: message_types_1.default.GQL_STOP });
            break;
        case message_types_1.default.GQL_CONNECTION_ACK:
            if (connectionContext.isLegacy) {
                messageToReturn = __assign(__assign({}, message), { type: message_types_1.default.INIT_SUCCESS });
            }
            break;
        case message_types_1.default.GQL_CONNECTION_ERROR:
            if (connectionContext.isLegacy) {
                messageToReturn = __assign(__assign({}, message), { type: message_types_1.default.INIT_FAIL, payload: message.payload.message ? { error: message.payload.message } : message.payload });
            }
            break;
        case message_types_1.default.GQL_ERROR:
            if (connectionContext.isLegacy) {
                messageToReturn = __assign(__assign({}, message), { type: message_types_1.default.SUBSCRIPTION_FAIL });
            }
            break;
        case message_types_1.default.GQL_DATA:
            if (connectionContext.isLegacy) {
                messageToReturn = __assign(__assign({}, message), { type: message_types_1.default.SUBSCRIPTION_DATA });
            }
            break;
        case message_types_1.default.GQL_COMPLETE:
            if (connectionContext.isLegacy) {
                messageToReturn = null;
            }
            break;
        case message_types_1.default.SUBSCRIPTION_SUCCESS:
            if (!connectionContext.isLegacy) {
                messageToReturn = null;
            }
            break;
        default:
            break;
    }
    return messageToReturn;
};
//# sourceMappingURL=parse-legacy-protocol.js.map