"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");

exports.__esModule = true;
exports.rebuildSchemaWithSitePage = rebuildSchemaWithSitePage;

var _schema = require("../schema");

var _reporter = _interopRequireDefault(require("gatsby-cli/lib/reporter"));

async function rebuildSchemaWithSitePage({
  parentSpan
}) {
  const activity = _reporter.default.activityTimer(`update schema`, {
    parentSpan
  });

  activity.start();
  await (0, _schema.rebuildWithSitePage)({
    parentSpan
  });
  activity.end();
}
//# sourceMappingURL=rebuild-schema-with-site-pages.js.map