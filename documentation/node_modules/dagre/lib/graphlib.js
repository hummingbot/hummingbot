/* global window */

var graphlib;

if (typeof require === "function") {
  try {
    graphlib = require("graphlib");
  } catch (e) {
    // continue regardless of error
  }
}

if (!graphlib) {
  graphlib = window.graphlib;
}

module.exports = graphlib;
