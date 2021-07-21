"use strict";

exports.__esModule = true;
exports.getLocalGatsbyVersion = void 0;

var _gatsbyTelemetry = require("gatsby-telemetry");

var _gatsbyCoreUtils = require("gatsby-core-utils");

const getLocalGatsbyVersion = () => {
  const version = (0, _gatsbyCoreUtils.getGatsbyVersion)();

  try {
    (0, _gatsbyTelemetry.setDefaultTags)({
      installedGatsbyVersion: version
    });
  } catch (e) {// ignore
  }

  return version;
};

exports.getLocalGatsbyVersion = getLocalGatsbyVersion;