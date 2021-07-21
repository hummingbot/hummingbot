"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
var pubsub_async_iterator_1 = require("./pubsub-async-iterator");
var PubSubEngine = (function () {
    function PubSubEngine() {
    }
    PubSubEngine.prototype.asyncIterator = function (triggers) {
        return new pubsub_async_iterator_1.PubSubAsyncIterator(this, triggers);
    };
    return PubSubEngine;
}());
exports.PubSubEngine = PubSubEngine;
//# sourceMappingURL=pubsub-engine.js.map