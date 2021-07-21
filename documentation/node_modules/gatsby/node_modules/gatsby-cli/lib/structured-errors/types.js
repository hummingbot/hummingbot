"use strict";

exports.__esModule = true;
exports.Type = exports.Level = void 0;
let Level;
exports.Level = Level;

(function (Level) {
  Level["ERROR"] = "ERROR";
  Level["WARNING"] = "WARNING";
  Level["INFO"] = "INFO";
  Level["DEBUG"] = "DEBUG";
})(Level || (exports.Level = Level = {}));

let Type;
exports.Type = Type;

(function (Type) {
  Type["GRAPHQL"] = "GRAPHQL";
  Type["CONFIG"] = "CONFIG";
  Type["WEBPACK"] = "WEBPACK";
  Type["PLUGIN"] = "PLUGIN";
})(Type || (exports.Type = Type = {}));