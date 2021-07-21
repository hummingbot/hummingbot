"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.addDataAttr = exports.extractId = void 0;
function extractId(href) {
    return href.replace(/^[a-z-]+:\/+?[^\/]+/, '') // Remove protocol & domain
        .replace(/[\?\&]livereload=\w+/, '') // Remove LiveReload cachebuster
        .replace(/^\//, '') // Remove root /
        .replace(/\.[a-zA-Z]+$/, '') // Remove simple extension
        .replace(/[^\.\w-]+/g, '-') // Replace illegal characters
        .replace(/\./g, ':'); // Replace dots with colons(for valid id)
}
exports.extractId = extractId;
function addDataAttr(options, tag) {
    for (var opt in tag.dataset) {
        if (tag.dataset.hasOwnProperty(opt)) {
            if (opt === 'env' || opt === 'dumpLineNumbers' || opt === 'rootpath' || opt === 'errorReporting') {
                options[opt] = tag.dataset[opt];
            }
            else {
                try {
                    options[opt] = JSON.parse(tag.dataset[opt]);
                }
                catch (_) { }
            }
        }
    }
}
exports.addDataAttr = addDataAttr;
//# sourceMappingURL=utils.js.map