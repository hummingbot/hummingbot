const fs = require("fs-extra");
const path = require("path");
const debug = require("debug")("gatsby-plugin-printer");
const genCodeBundle = require("./gen-code-bundle");
const runScreenshots = require("./run-screenshots");

const defaultOutputDir = `gatsby-plugin-printer/images`;

exports.createSchemaCustomization = ({ actions, schema }) => {
  const { createTypes } = actions;
  createTypes(`
    type Printer implements Node {
      id: ID!
      fileName: String!
      outputDir: String!
      data: JSON!
      component: String!
    }
  `);
};
exports.onPostBuild = async ({ graphql, cache }, pluginOptions) => {
  const data = await graphql(`
    {
      allPrinter {
        group(field: component) {
          component: fieldValue
          nodes {
            id
            fileName
            outputDir
            data
          }
        }
      }
    }
  `).then(r => {
    if (r.errors) {
      throw new Error(r.errors.join(`, `));
    }

    return r.data;
  });

  await fs.mkdirp(path.join("./public", defaultOutputDir));

  debug("num printer groups", data.allPrinter.group.length);

  await Promise.all(
    data.allPrinter.group.map(async ({ component, nodes }) => {
      debug(`processing '${component}'`);
      const code = await genCodeBundle({ componentPath: component });
      debug(`running ${nodes.length} nodes with ${component}`);
      await runScreenshots(
        {
          data: nodes.map(node => ({
            ...node,
            data: JSON.parse(node.data)
          })),
          code
        },
        pluginOptions.puppeteerLaunchOptions
      );
    })
  );
};
