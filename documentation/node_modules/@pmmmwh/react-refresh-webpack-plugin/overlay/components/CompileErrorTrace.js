const ansiHTML = require('ansi-html');
const HtmlEntities = require('html-entities');
const theme = require('../theme');
const formatFilename = require('../utils/formatFilename');

ansiHTML.setColors(theme);

const entities = new HtmlEntities.Html5Entities();

/**
 * @typedef {Object} CompileErrorTraceProps
 * @property {string} errorMessage
 */

/**
 * A formatter that turns Webpack compile error messages into highlighted HTML source traces.
 * @param {Document} document
 * @param {HTMLElement} root
 * @param {CompileErrorTraceProps} props
 * @returns {void}
 */
function CompileErrorTrace(document, root, props) {
  const errorParts = props.errorMessage.split('\n');
  const errorMessage = errorParts
    .splice(1, 1)[0]
    // Strip filename from the error message
    .replace(/^(.*:)\s.*:(\s.*)$/, '$1$2');
  errorParts[0] = formatFilename(errorParts[0]);
  errorParts.unshift(errorMessage);

  const stackContainer = document.createElement('pre');
  stackContainer.innerHTML = entities.decode(ansiHTML(entities.encode(errorParts.join('\n'))));
  stackContainer.style.fontFamily = [
    '"Operator Mono SSm"',
    '"Operator Mono"',
    '"Fira Code Retina"',
    '"Fira Code"',
    '"FiraCode-Retina"',
    '"Andale Mono"',
    '"Lucida Console"',
    'Menlo',
    'Consolas',
    'Monaco',
    'monospace',
  ].join(', ');
  stackContainer.style.margin = '0';
  stackContainer.style.whiteSpace = 'pre-wrap';

  root.appendChild(stackContainer);
}

module.exports = CompileErrorTrace;
