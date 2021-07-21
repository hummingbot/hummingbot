"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");

exports.__esModule = true;
exports.getErrorFormatter = getErrorFormatter;
exports.createErrorFromString = createErrorFromString;
exports.sanitizeStructuredStackTrace = void 0;

var _prettyError = _interopRequireDefault(require("pretty-error"));

var _prepareStackTrace = require("./prepare-stack-trace");

var _gatsbyCoreUtils = require("gatsby-core-utils");

const packagesToSkip = [`core-js`, `bluebird`, `regenerator-runtime`, `graphql`];
const packagesToSkipTest = new RegExp(`node_modules[\\/](${packagesToSkip.join(`|`)})`); // TO-DO: move this this out of this file (and probably delete this file completely)
// it's here because it re-implements similar thing as `pretty-error` already does

const sanitizeStructuredStackTrace = stack => {
  // first filter out not useful call sites
  stack = stack.filter(callSite => {
    if (!callSite.getFileName()) {
      return false;
    }

    if (packagesToSkipTest.test(callSite.getFileName())) {
      return false;
    }

    if (callSite.getFileName().includes(`asyncToGenerator.js`)) {
      return false;
    }

    if ((0, _gatsbyCoreUtils.isNodeInternalModulePath)(callSite.getFileName())) {
      return false;
    }

    return true;
  }); // then sanitize individual call site objects to make sure we don't
  // emit objects with extra fields that won't be handled by consumers

  return stack.map(callSite => {
    return {
      fileName: callSite.getFileName(),
      functionName: callSite.getFunctionName(),
      columnNumber: callSite.getColumnNumber(),
      lineNumber: callSite.getLineNumber()
    };
  });
};

exports.sanitizeStructuredStackTrace = sanitizeStructuredStackTrace;

function getErrorFormatter() {
  const prettyError = new _prettyError.default();
  const baseRender = prettyError.render;
  prettyError.skipNodeFiles();
  prettyError.skipPackage(`regenerator-runtime`, `graphql`, `core-js` // `static-site-generator-webpack-plugin`,
  // `tapable`, // webpack
  ); // @ts-ignore the type defs in prettyError are wrong

  prettyError.skip(traceLine => {
    if (traceLine && traceLine.file === `asyncToGenerator.js`) return true;
    return false;
  });
  prettyError.appendStyle({
    "pretty-error": {
      marginTop: 1
    },
    "pretty-error > header": {
      background: `red`
    },
    "pretty-error > header > colon": {
      color: `white`
    }
  });

  if (process.env.FORCE_COLOR === `0`) {
    prettyError.withoutColors();
  }

  prettyError.render = err => {
    if (Array.isArray(err)) {
      return err.map(e => prettyError.render(e)).join(`\n`);
    }

    let rendered = baseRender.call(prettyError, err);
    if (`codeFrame` in err) rendered = `\n${err.codeFrame}\n${rendered}`;
    return rendered;
  };

  return prettyError;
}
/**
 * Convert a stringified webpack compilation error back into
 * an Error instance so it can be formatted properly
 */


async function createErrorFromString(errorStr = ``, sourceMapFile) {
  let [message, ...rest] = errorStr.split(/\r\n|[\n\r]/g); // pull the message from the first line then remove the `Error:` prefix
  // FIXME: when https://github.com/AriaMinaei/pretty-error/pull/49 is merged

  message = message.replace(/^(Error:)/, ``);
  const error = new Error(message);
  error.stack = [message, rest.join(`\n`)].join(`\n`);
  error.name = `WebpackError`;

  try {
    if (sourceMapFile) {
      return await (0, _prepareStackTrace.prepareStackTrace)(error, sourceMapFile);
    }
  } catch (err) {// don't shadow a real error because of a parsing issue
  }

  return error;
}