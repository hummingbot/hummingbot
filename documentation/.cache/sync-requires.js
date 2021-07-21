const { hot } = require("react-hot-loader/root")

// prefer default export if available
const preferDefault = m => (m && m.default) || m


exports.components = {
  "component---cache-dev-404-page-js": hot(preferDefault(require("/Users/dennis/Desktop/GitHub/hummingbot-docs/.cache/dev-404-page.js"))),
  "component---node-modules-gatsby-theme-apollo-core-src-pages-404-js": hot(preferDefault(require("/Users/dennis/Desktop/GitHub/hummingbot-docs/node_modules/gatsby-theme-apollo-core/src/pages/404.js"))),
  "component---src-gatsby-theme-apollo-docs-components-template-js": hot(preferDefault(require("/Users/dennis/Desktop/GitHub/hummingbot-docs/src/gatsby-theme-apollo-docs/components/template.js")))
}

