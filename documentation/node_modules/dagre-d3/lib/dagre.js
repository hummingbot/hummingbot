/* global window */

var dagre;

if (typeof require === "function") {
  try {
    dagre = require("dagre");
  } catch (e) {
    // continue regardless of error
  }
}

if (!dagre) {
  dagre = window.dagre;
}

module.exports = dagre;
