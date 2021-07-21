"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");

exports.__esModule = true;
exports.default = startTelemetryServer;

var _express = _interopRequireDefault(require("express"));

var _bodyParser = _interopRequireDefault(require("body-parser"));

var _cors = _interopRequireDefault(require("cors"));

var _gatsbyTelemetry = require("gatsby-telemetry");

/*
 * This exposes gatsby-telemetry functions over HTTP. POST an array of arguments to the path.
 * For example:
 * curl -X POST http://localhost:2345/setVersion
 *   -H "Content-Type: application/json"
 *   -d "[\"1.2.3\"]"
 */
(0, _gatsbyTelemetry.setDefaultComponentId)(`gatsby-admin`); // These routes will exist in the API at the keys, e.g.
// http://localhost:1234/trackEvent

const ROUTES = {
  trackEvent: _gatsbyTelemetry.trackCli,
  trackError: _gatsbyTelemetry.trackError
};
const app = (0, _express.default)();
app.use((0, _cors.default)()); // Overview over all possible routes at /

app.get(`/`, (req, res) => {
  res.set(`Content-Type`, `text/html`);
  res.send(`<ul>
      ${Object.keys(ROUTES).map(route => `<li><a href="/${route}">/${route}</a></li>`).join(`\n`)}
    </ul>`);
});
Object.keys(ROUTES).map(route => {
  app.post(`/${route}`, _bodyParser.default.json(), (req, res) => {
    if (!req.body || !Array.isArray(req.body)) {
      res.json({
        status: `error`,
        error: `Please provide a body array with the arguments for the function.`
      });
      return;
    }

    try {
      ROUTES[route](...req.body);
    } catch (err) {
      console.error(err);
      res.json({
        status: `error`,
        error: err.message
      });
      return;
    }

    res.json({
      status: `success`
    });
  });
});

function startTelemetryServer(port) {
  (0, _gatsbyTelemetry.startBackgroundUpdate)();
  app.listen(port);
}
//# sourceMappingURL=telemetry-server.js.map