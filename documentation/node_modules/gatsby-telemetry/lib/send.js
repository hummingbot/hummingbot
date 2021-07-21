"use strict";

var _telemetry = require("./telemetry");

const instance = new _telemetry.AnalyticsTracker();

function flush() {
  instance.sendEvents().catch(_e => {// ignore
  });
}

flush();