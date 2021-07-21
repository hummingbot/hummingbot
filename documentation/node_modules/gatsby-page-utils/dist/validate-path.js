"use strict";

exports.__esModule = true;
exports.validatePath = validatePath;

var _path = require("path");

var _micromatch = require("micromatch");

var tsDeclarationExtTest = /\.d\.tsx?$/;
var jsonYamlExtTest = /\.(json|ya?ml)$/; // https://github.com/facebook/jest/blob/v24.0.0-alpha.4/packages/jest-config/src/Defaults.js#L71

function isTestFile(filePath) {
  var testPatterns = ["**/__tests__/**/*.(js|ts|jsx|tsx)", "**/(*.)+(spec|test).(js|ts|jsx|tsx)"];
  return (0, _micromatch.isMatch)(filePath, testPatterns);
}

function validatePath(path) {
  // Disallow paths starting with an underscore (_) or dot (.)
  // and template-.
  // and .d.ts
  var parsedPath = (0, _path.parse)(path);
  return parsedPath.name.slice(0, 1) !== "_" && parsedPath.name.slice(0, 1) !== "." && parsedPath.name.slice(0, 9) !== "template-" && !tsDeclarationExtTest.test(parsedPath.base) && !jsonYamlExtTest.test(parsedPath.base) && !isTestFile(path.replace(/\\/g, "/"));
}