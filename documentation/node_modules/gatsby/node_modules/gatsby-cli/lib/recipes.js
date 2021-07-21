"use strict";

exports.__esModule = true;
exports.recipesHandler = recipesHandler;

var _gatsbyTelemetry = require("gatsby-telemetry");

var _gatsbyRecipes = require("gatsby-recipes");

async function recipesHandler(projectRoot, recipe, develop, install) {
  (0, _gatsbyTelemetry.trackCli)(`RECIPE_RUN`, {
    name: recipe
  });
  const graphql = await (0, _gatsbyRecipes.startGraphQLServer)(projectRoot);
  return (0, _gatsbyRecipes.recipesHandler)({
    recipe,
    isDevelopMode: develop,
    isInstallMode: install,
    graphqlPort: graphql.port,
    projectRoot
  });
}