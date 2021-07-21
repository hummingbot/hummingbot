const { BABEL_ENV, NODE_ENV } = process.env;
const cjs = BABEL_ENV === "cjs" || NODE_ENV === "test";

module.exports = {
  presets: [
    ["@babel/env", { loose: true, exclude: [/transform-typeof-symbol/] }],
    "@babel/flow"
  ],
  plugins: [cjs && "add-module-exports", "annotate-pure-calls"].filter(Boolean)
};
