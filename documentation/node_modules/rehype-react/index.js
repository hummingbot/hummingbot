'use strict';

/* Dependencies. */
var has = require('has');
var toH = require('hast-to-hyperscript');
var tableCellStyle = require('@mapbox/hast-util-table-cell-style');

/* Expose `rehype-react`. */
module.exports = rehype2react;

/**
 * Attach a react compiler.
 *
 * @param {Unified} processor - Instance.
 * @param {Object?} [options]
 * @param {Object?} [options.components]
 *   - Components.
 * @param {string?} [options.prefix]
 *   - Key prefix.
 * @param {Function?} [options.createElement]
 *   - `h()`.
 */
function rehype2react(options) {
  var settings = options || {};
  var createElement = settings.createElement;
  var components = settings.components || {};

  this.Compiler = compiler;

  /* Compile HAST to React. */
  function compiler(node) {
    if (node.type === 'root') {
      if (node.children.length === 1 && node.children[0].type === 'element') {
        node = node.children[0];
      } else {
        node = {
          type: 'element',
          tagName: 'div',
          properties: node.properties || {},
          children: node.children
        };
      }
    }

    return toH(h, tableCellStyle(node), settings.prefix);
  }

  /* Wrap `createElement` to pass components in. */
  function h(name, props, children) {
    var component = has(components, name) ? components[name] : name;
    return createElement(component, props, children);
  }
}
