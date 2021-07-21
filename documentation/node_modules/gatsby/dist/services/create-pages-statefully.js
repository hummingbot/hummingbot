"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");

exports.__esModule = true;
exports.createPagesStatefully = createPagesStatefully;

var _reporter = _interopRequireDefault(require("gatsby-cli/lib/reporter"));

var _apiRunnerNode = _interopRequireDefault(require("../utils/api-runner-node"));

async function createPagesStatefully({
  parentSpan,
  gatsbyNodeGraphQLFunction,
  deferNodeMutation
}) {
  // A variant on createPages for plugins that want to
  // have full control over adding/removing pages. The normal
  // "createPages" API is called every time (during development)
  // that data changes.
  const activity = _reporter.default.activityTimer(`createPagesStatefully`, {
    parentSpan
  });

  activity.start();
  await (0, _apiRunnerNode.default)(`createPagesStatefully`, {
    graphql: gatsbyNodeGraphQLFunction,
    traceId: `initial-createPagesStatefully`,
    waitForCascadingActions: true,
    parentSpan: activity.span,
    deferNodeMutation
  }, {
    activity
  });
  activity.end();
}
//# sourceMappingURL=create-pages-statefully.js.map