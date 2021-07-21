"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
function makeRegistry(base) {
    return {
        _data: {},
        add: function (name, func) {
            // precautionary case conversion, as later querying of
            // the registry by function-caller uses lower case as well.
            name = name.toLowerCase();
            if (this._data.hasOwnProperty(name)) {
                // TODO warn
            }
            this._data[name] = func;
        },
        addMultiple: function (functions) {
            var _this = this;
            Object.keys(functions).forEach(function (name) {
                _this.add(name, functions[name]);
            });
        },
        get: function (name) {
            return this._data[name] || (base && base.get(name));
        },
        getLocalFunctions: function () {
            return this._data;
        },
        inherit: function () {
            return makeRegistry(this);
        },
        create: function (base) {
            return makeRegistry(base);
        }
    };
}
exports.default = makeRegistry(null);
//# sourceMappingURL=function-registry.js.map