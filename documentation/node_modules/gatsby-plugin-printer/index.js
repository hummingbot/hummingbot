const crypto = require("crypto");
const { store } = require("gatsby/dist/redux");
const apiRunnerNode = require(`gatsby/dist/utils/api-runner-node`);
const genCodeBundle = require("./gen-code-bundle");
const runScreenshots = require("./run-screenshots");

const createPrinterNode = ({ id, fileName, outputDir, data, component }) => {
  const fieldData = {
    id,
    fileName,
    outputDir,
    data: JSON.stringify(data),
    component
  };

  const node = {
    ...fieldData,

    // Required fields.
    id,
    parent: null,
    children: [],
    internal: {
      type: `Printer`,
      contentDigest: crypto
        .createHash(`md5`)
        .update(JSON.stringify(fieldData))
        .digest(`hex`),
      // mediaType: `text/markdown`, // optional
      content: JSON.stringify(fieldData), // optional
      description: `Printer: node that contains data to be printed into an image`, // optional
      owner: "gatsby-plugin-printer"
    }
  };

  store.dispatch({
    type: `CREATE_NODE`,
    payload: node
  });
  // we're being sneaky, so we have to called onCreateNode for this new node
  return apiRunnerNode(`onCreateNode`, {
    node
    // traceId,
    // parentSpan,
    // traceTags: { nodeId: node.id, nodeType: node.internal.type },
  });
  return node.id;
};

module.exports = {
  createPrinterNode,
  runScreenshots: async (
    { data, component, outputDir },
    puppeteerLaunchOptions
  ) => {
    const mappedData = data.map(obj => {
      if (!Boolean(obj.id)) {
        throw new Error(
          `object requires id in runScreenshots(). object is: \n\n ${JSON.stringify(
            obj,
            null,
            2
          )}`
        );
      }

      const newObj = { ...obj, data: obj };
      if (!Boolean(obj.outputDir)) {
        if (!outputDir) {
          throw new Error(`object requires an 'outputDir' field OR an 'outputDir' needs to be supplied as an argument to 'runScreenshots'
          
${JSON.stringify(obj, null, 2)}`);
        }
        newObj.outputDir = outputDir;
      }

      if (!Boolean(obj.fileName)) {
        newObj.fileName = obj.id;
      }

      return newObj;
    });
    const code = await genCodeBundle({ componentPath: component });
    await runScreenshots({ data: mappedData, code }, puppeteerLaunchOptions);
  }
};
