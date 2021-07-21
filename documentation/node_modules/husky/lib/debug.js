"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
function debug(...args) {
    if (['1', 'true'].includes(process.env.HUSKY_DEBUG || '')) {
        console.log('husky:debug', ...args);
    }
}
exports.debug = debug;
