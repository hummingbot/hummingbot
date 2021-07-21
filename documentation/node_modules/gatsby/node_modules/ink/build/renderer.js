"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;

var _yogaLayoutPrebuilt = _interopRequireDefault(require("yoga-layout-prebuilt"));

var _output = _interopRequireDefault(require("./output"));

var _dom = require("./dom");

var _buildLayout = _interopRequireDefault(require("./build-layout"));

var _renderNodeToOutput = _interopRequireDefault(require("./render-node-to-output"));

var _calculateWrappedText = _interopRequireDefault(require("./calculate-wrapped-text"));

function _interopRequireDefault(obj) { return obj && obj.__esModule ? obj : { default: obj }; }

// Since <Static> components can be placed anywhere in the tree, this helper finds and returns them
const getStaticNodes = element => {
  const staticNodes = [];

  for (const childNode of element.childNodes) {
    if (childNode.unstable__static) {
      staticNodes.push(childNode);
    }

    if (Array.isArray(childNode.childNodes) && childNode.childNodes.length > 0) {
      staticNodes.push(...getStaticNodes(childNode));
    }
  }

  return staticNodes;
}; // Build layout, apply styles, build text output of all nodes and return it


var _default = ({
  terminalWidth
}) => {
  const config = _yogaLayoutPrebuilt.default.Config.create(); // Used to free up memory used by last Yoga node tree


  let lastYogaNode;
  let lastStaticYogaNode;
  return node => {
    if (lastYogaNode) {
      lastYogaNode.freeRecursive();
    }

    if (lastStaticYogaNode) {
      lastStaticYogaNode.freeRecursive();
    }

    const staticElements = getStaticNodes(node);

    if (staticElements.length > 1) {
      if (process.env.NODE_ENV !== 'production') {
        console.error('Warning: There can only be one <Static> component');
      }
    } // <Static> component must be built and rendered separately, so that the layout of the other output is unaffected


    let staticOutput;

    if (staticElements.length === 1) {
      const rootNode = (0, _dom.createNode)('root');
      (0, _dom.appendStaticNode)(rootNode, staticElements[0]);
      const {
        yogaNode: staticYogaNode
      } = (0, _buildLayout.default)(rootNode, {
        config,
        terminalWidth,
        skipStaticElements: false
      });
      staticYogaNode.calculateLayout(_yogaLayoutPrebuilt.default.UNDEFINED, _yogaLayoutPrebuilt.default.UNDEFINED, _yogaLayoutPrebuilt.default.DIRECTION_LTR);
      (0, _calculateWrappedText.default)(rootNode);
      staticYogaNode.calculateLayout(_yogaLayoutPrebuilt.default.UNDEFINED, _yogaLayoutPrebuilt.default.UNDEFINED, _yogaLayoutPrebuilt.default.DIRECTION_LTR); // Save current Yoga node tree to free up memory later

      lastStaticYogaNode = staticYogaNode;
      staticOutput = new _output.default({
        width: staticYogaNode.getComputedWidth(),
        height: staticYogaNode.getComputedHeight()
      });
      (0, _renderNodeToOutput.default)(rootNode, staticOutput, {
        skipStaticElements: false
      });
    }

    const {
      yogaNode
    } = (0, _buildLayout.default)(node, {
      config,
      terminalWidth,
      skipStaticElements: true
    });
    yogaNode.calculateLayout(_yogaLayoutPrebuilt.default.UNDEFINED, _yogaLayoutPrebuilt.default.UNDEFINED, _yogaLayoutPrebuilt.default.DIRECTION_LTR);
    (0, _calculateWrappedText.default)(node);
    yogaNode.calculateLayout(_yogaLayoutPrebuilt.default.UNDEFINED, _yogaLayoutPrebuilt.default.UNDEFINED, _yogaLayoutPrebuilt.default.DIRECTION_LTR); // Save current node tree to free up memory later

    lastYogaNode = yogaNode;
    const output = new _output.default({
      width: yogaNode.getComputedWidth(),
      height: yogaNode.getComputedHeight()
    });
    (0, _renderNodeToOutput.default)(node, output, {
      skipStaticElements: true
    });
    return {
      output: output.get(),
      outputHeight: output.getHeight(),
      staticOutput: staticOutput ? `${staticOutput.get()}\n` : undefined
    };
  };
};

exports.default = _default;