"use strict";

/* Code borrowed and based on
 * https://github.com/evanw/node-source-map-support/blob/master/source-map-support.js
 */

var _require = require(`fs`),
    readFileSync = _require.readFileSync;

var babelCodeFrame = require(`babel-code-frame`);
var stackTrace = require(`stack-trace`);

var _require2 = require(`source-map`),
    SourceMapConsumer = _require2.SourceMapConsumer;

module.exports = function prepareStackTrace(error, source) {
  var map = new SourceMapConsumer(readFileSync(source, `utf8`));
  var stack = stackTrace.parse(error).map(function (frame) {
    return wrapCallSite(map, frame);
  }).filter(function (frame) {
    return !frame.getFileName() || !frame.getFileName().match(/^webpack:\/+webpack\//);
  });

  error.codeFrame = getErrorSource(map, stack[0]);
  error.stack = `${error.name}: ${error.message}\n` + stack.map(function (frame) {
    return `    at ${frame}`;
  }).join(`\n`);
};

function getErrorSource(map, topFrame) {
  var source = map.sourceContentFor(topFrame.getFileName(), true);
  return source && babelCodeFrame(source, topFrame.getLineNumber(), topFrame.getColumnNumber(), {
    highlightCode: true
  });
}

function wrapCallSite(map, frame) {
  var source = frame.getFileName();
  if (!source) return frame;

  var position = getPosition(map, frame);
  if (!position.source) return frame;

  frame.getFileName = function () {
    return position.source;
  };
  frame.getLineNumber = function () {
    return position.line;
  };
  frame.getColumnNumber = function () {
    return position.column + 1;
  };
  frame.getScriptNameOrSourceURL = function () {
    return position.source;
  };
  frame.toString = CallSiteToString;
  return frame;
}

function getPosition(map, frame) {
  var source = frame.getFileName();
  var line = frame.getLineNumber();
  var column = frame.getColumnNumber();
  return map.originalPositionFor({ source, line, column });
}

// This is copied almost verbatim from the V8 source code at
// https://code.google.com/p/v8/source/browse/trunk/src/messages.js.
function CallSiteToString() {
  var fileName = void 0;
  var fileLocation = ``;
  if (this.isNative()) {
    fileLocation = `native`;
  } else {
    fileName = this.scriptNameOrSourceURL && this.scriptNameOrSourceURL() || this.getFileName();

    if (!fileName && this.isEval && this.isEval()) {
      fileLocation = `${this.getEvalOrigin()}, `;
    }

    if (fileName) {
      fileLocation += fileName.replace(/^webpack:\/+/, ``);
    } else {
      // Source code does not originate from a file and is not native, but we
      // can still get the source position inside the source string, e.g. in
      // an eval string.
      fileLocation += `<anonymous>`;
    }
    var lineNumber = this.getLineNumber();
    if (lineNumber != null) {
      fileLocation += `:${lineNumber}`;
      var columnNumber = this.getColumnNumber();
      if (columnNumber) {
        fileLocation += `:${columnNumber}`;
      }
    }
  }

  var line = ``;
  var functionName = this.getFunctionName();
  var addSuffix = true;
  var isConstructor = this.isConstructor && this.isConstructor();
  var methodName = this.getMethodName();
  var typeName = this.getTypeName();
  var isMethodCall = methodName && !(this.isToplevel && this.isToplevel() || isConstructor);
  if (isMethodCall && functionName) {
    if (functionName) {
      if (typeName && functionName.indexOf(typeName) != 0) {
        line += `${typeName}.`;
      }
      line += functionName;
      if (methodName && functionName.indexOf(`.` + methodName) != functionName.length - methodName.length - 1) {
        line += ` [as ${methodName}]`;
      }
    } else {
      line += typeName + `.` + (methodName || `<anonymous>`);
    }
  } else if (typeName && !functionName) {
    line += typeName + `.` + (methodName || `<anonymous>`);
  } else if (isConstructor) {
    line += `new ` + (functionName || `<anonymous>`);
  } else if (functionName) {
    line += functionName;
  } else {
    line += fileLocation;
    addSuffix = false;
  }
  if (addSuffix) line += ` (${fileLocation})`;
  return line;
}