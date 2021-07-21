exports = global.fetch // To enable: import fetch from 'cross-fetch'
exports.default = global.fetch // For TypeScript consumers without esModuleInterop.
exports.fetch = global.fetch // To enable: import {fetch} from 'cross-fetch'
exports.Headers = global.Headers
exports.Request = global.Request
exports.Response = global.Response

module.exports = exports
