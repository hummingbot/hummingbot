"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");

var _repl = _interopRequireDefault(require("repl"));

var _graphql = require("graphql");

var _bootstrap = require("../bootstrap");

var _gatsbyTelemetry = require("gatsby-telemetry");

var _nodes = require("../redux/nodes");

var _nodes2 = require("../db/nodes");

var _redux = require("../redux");

module.exports = async program => {
  (0, _gatsbyTelemetry.trackCli)(`REPL_START`); // run bootstrap

  await (0, _bootstrap.bootstrap)({
    program
  }); // get all the goodies from the store

  const {
    schema,
    config,
    babelrc,
    pages,
    components,
    staticQueryComponents
  } = _redux.store.getState();

  const nodes = (0, _nodes.getNodes)();

  const query = async query => {
    const result = await (0, _graphql.graphql)(schema, query, {}, {}, {});
    console.log(`query result: ${JSON.stringify(result)}`);
  }; // init new repl


  const _ = _repl.default.start({
    prompt: `gatsby > `
  }); // set some globals to make life easier


  _.context.babelrc = babelrc;
  _.context.components = components;
  _.context.getNode = _nodes.getNode;
  _.context.getNodes = _nodes.getNodes;
  _.context.getNodesByType = _nodes.getNodesByType;
  _.context.loadNodeContent = _nodes2.loadNodeContent;
  _.context.nodes = [...nodes.entries()];
  _.context.pages = [...pages.entries()];
  _.context.graphql = query;
  _.context.schema = schema;
  _.context.siteConfig = config;
  _.context.staticQueries = staticQueryComponents;

  _.on(`exit`, () => {
    (0, _gatsbyTelemetry.trackCli)(`REPL_STOP`);
    process.exit(0);
  });
};
//# sourceMappingURL=repl.js.map