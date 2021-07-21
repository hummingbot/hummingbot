"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.config = {
    onError: function (e) { return console.error(e); },
};
exports.setConfig = function (conf) {
    Object.assign(exports.config, conf);
};
