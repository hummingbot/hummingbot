"use strict";
var __extends = (this && this.__extends) || (function () {
    var extendStatics = Object.setPrototypeOf ||
        ({ __proto__: [] } instanceof Array && function (d, b) { d.__proto__ = b; }) ||
        function (d, b) { for (var p in b) if (b.hasOwnProperty(p)) d[p] = b[p]; };
    return function (d, b) {
        extendStatics(d, b);
        function __() { this.constructor = d; }
        d.prototype = b === null ? Object.create(b) : (__.prototype = b.prototype, new __());
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
var events_1 = require("events");
var pubsub_engine_1 = require("./pubsub-engine");
var PubSub = (function (_super) {
    __extends(PubSub, _super);
    function PubSub(options) {
        if (options === void 0) { options = {}; }
        var _this = _super.call(this) || this;
        _this.ee = options.eventEmitter || new events_1.EventEmitter();
        _this.subscriptions = {};
        _this.subIdCounter = 0;
        return _this;
    }
    PubSub.prototype.publish = function (triggerName, payload) {
        this.ee.emit(triggerName, payload);
        return Promise.resolve();
    };
    PubSub.prototype.subscribe = function (triggerName, onMessage) {
        this.ee.addListener(triggerName, onMessage);
        this.subIdCounter = this.subIdCounter + 1;
        this.subscriptions[this.subIdCounter] = [triggerName, onMessage];
        return Promise.resolve(this.subIdCounter);
    };
    PubSub.prototype.unsubscribe = function (subId) {
        var _a = this.subscriptions[subId], triggerName = _a[0], onMessage = _a[1];
        delete this.subscriptions[subId];
        this.ee.removeListener(triggerName, onMessage);
    };
    return PubSub;
}(pubsub_engine_1.PubSubEngine));
exports.PubSub = PubSub;
//# sourceMappingURL=pubsub.js.map