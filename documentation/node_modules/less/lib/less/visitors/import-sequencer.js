"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
var ImportSequencer = /** @class */ (function () {
    function ImportSequencer(onSequencerEmpty) {
        this.imports = [];
        this.variableImports = [];
        this._onSequencerEmpty = onSequencerEmpty;
        this._currentDepth = 0;
    }
    ImportSequencer.prototype.addImport = function (callback) {
        var importSequencer = this;
        var importItem = {
            callback: callback,
            args: null,
            isReady: false
        };
        this.imports.push(importItem);
        return function () {
            var args = [];
            for (var _i = 0; _i < arguments.length; _i++) {
                args[_i] = arguments[_i];
            }
            importItem.args = Array.prototype.slice.call(args, 0);
            importItem.isReady = true;
            importSequencer.tryRun();
        };
    };
    ImportSequencer.prototype.addVariableImport = function (callback) {
        this.variableImports.push(callback);
    };
    ImportSequencer.prototype.tryRun = function () {
        this._currentDepth++;
        try {
            while (true) {
                while (this.imports.length > 0) {
                    var importItem = this.imports[0];
                    if (!importItem.isReady) {
                        return;
                    }
                    this.imports = this.imports.slice(1);
                    importItem.callback.apply(null, importItem.args);
                }
                if (this.variableImports.length === 0) {
                    break;
                }
                var variableImport = this.variableImports[0];
                this.variableImports = this.variableImports.slice(1);
                variableImport();
            }
        }
        finally {
            this._currentDepth--;
        }
        if (this._currentDepth === 0 && this._onSequencerEmpty) {
            this._onSequencerEmpty();
        }
    };
    return ImportSequencer;
}());
exports.default = ImportSequencer;
//# sourceMappingURL=import-sequencer.js.map