# React Refresh Webpack Plugin

[![Latest Version](https://img.shields.io/npm/v/@pmmmwh/react-refresh-webpack-plugin/latest)](https://www.npmjs.com/package/@pmmmwh/react-refresh-webpack-plugin/v/latest)
[![Next Version](https://img.shields.io/npm/v/@pmmmwh/react-refresh-webpack-plugin/next)](https://www.npmjs.com/package/@pmmmwh/react-refresh-webpack-plugin/v/next)
[![CircleCI](https://img.shields.io/circleci/project/github/pmmmwh/react-refresh-webpack-plugin/main)](https://app.circleci.com/pipelines/github/pmmmwh/react-refresh-webpack-plugin)
[![License](https://img.shields.io/github/license/pmmmwh/react-refresh-webpack-plugin)](./LICENSE)

An **EXPERIMENTAL** Webpack plugin to enable "Fast Refresh" (also previously known as _Hot Reloading_) for React components.

## Prerequisites

First and foremost, this plugin is not 100% stable.
We're working towards a stable v1 release, and we've been testing the plugin quite extensively;
but since it is still pretty young, there might still be some unknown edge cases.

There are no breaking changes planned for the v1 release,
but they might still happen if we hit some significant road blockers.

Also, ensure that you are using the minimum supported versions of the plugin's peer dependencies -
older versions unfortunately do not contain code to orchestrate "Fast Refresh",
and thus cannot be made compatible.

| Dependency         | Minimum                                            | Best       |
| ------------------ | -------------------------------------------------- | ---------- |
| `react`            | `16.9.0`                                           | `16.13.0`+ |
| `react-dom`        | `16.9.0`                                           | `16.13.0`+ |
| `react-reconciler` | `0.22.0`                                           | `0.25.0`+  |
| `webpack`          | `4.0.0` (for `0.3.x`)<br />`4.43.0` (for `0.4.x`+) | `4.43.0`+  |

> You only need `react-dom` if you're rendering to the DOM.

> You only need to check for `react-reconciler` if you use custom reconcilers like `react-three-fiber`.
> You should check their `package.json` to make sure they use a compatible version instead of installing `react-reconciler` yourself.
> If the reconcilers are not compatible, please create an issue at their repository.

## Installation

With all prerequisites met, you can install the plugin with one of the commands below:

```sh
# if you prefer npm
npm install -D @pmmmwh/react-refresh-webpack-plugin react-refresh

# if you prefer yarn
yarn add -D @pmmmwh/react-refresh-webpack-plugin react-refresh

# if you prefer pnpm
pnpm add -D @pmmmwh/react-refresh-webpack-plugin react-refresh
```

The plugin depends on a package from the React team - `react-refresh`,
so you will have to install and configure it separately as demonstrated in the [Usage](#usage) section, too.

### TypeScript

TypeScript support is available out-of-the-box for those who use `webpack.config.ts` :tada:!

For that you will have to install `type-fest` as a development peer dependency with one of the commands below:

```sh
# if you prefer npm
npm install -D type-fest

# if you prefer yarn
yarn add -D type-fest

# if you prefer pnpm
pnpm add -D type-fest
```

## Usage

The most basic setup to enable "Fast Refresh" is to update your `webpack.config.js` (or `.ts`) as follows:

```js
const ReactRefreshWebpackPlugin = require('@pmmmwh/react-refresh-webpack-plugin');
const webpack = require('webpack');
// ... your other imports

const isDevelopment = process.env.NODE_ENV !== 'production';

module.exports = {
  // It is suggested to run both `react-refresh/babel` and the plugin in the `development` mode only,
  // even though both of them have optimisations in place to do nothing in the `production` mode.
  // If you would like to override Webpack's defaults for modes, you can also use the `none` mode -
  // you then will need to set `forceEnable: true` in the plugin's options.
  mode: isDevelopment ? 'development' : 'production',
  module: {
    rules: [
      // ... other rules
      {
        test: /\.[jt]sx?$/,
        exclude: /node_modules/,
        use: [
          // ... other loaders
          {
            loader: require.resolve('babel-loader'),
            options: {
              // ... other options
              plugins: [
                // ... other plugins
                isDevelopment && require.resolve('react-refresh/babel'),
              ].filter(Boolean),
            },
          },
        ],
      },
    ],
  },
  plugins: [
    // ... other plugins
    isDevelopment && new webpack.HotModuleReplacementPlugin(),
    isDevelopment && new ReactRefreshWebpackPlugin(),
  ].filter(Boolean),
  // ... other configuration options
};
```

You might want to further tweak the configuration to accommodate your setup:

- `isDevelopment`

  In this example we've shown the simple way of splitting up `development` and `production` builds with the `NODE_ENV` environment variable.
  It will default to `true` (i.e. `development` mode) when `NODE_ENV` is not available from the environment.

  In practice though, you might want to wire this up differently,
  like [using a function config](https://webpack.js.org/configuration/configuration-types/#exporting-a-function) or using multiple configuration files.

- `webpack.HotModuleReplacamentPlugin`

  If you use `webpack-dev-server` or `webpack-plugin-serve`,
  you can set `devServer.hot`/`devServer.hotOnly` and `hmr` to `true` respectively,
  instead of adding the HMR plugin to your plugin list.

> Note: If you are using TypeScript (instead of Babel) as a transpiler, you will still need to use `babel-loader` to process your source code.
> Check out this [sample project](https://github.com/pmmmwh/react-refresh-webpack-plugin/tree/main/examples/typescript-without-babel) on how to set this up.

### Integration Support for Overlay

Officially, `webpack-dev-server`, `webpack-hot-middleware` and `webpack-plugin-serve` aer supported out of the box -
you just have to set the [`overlay.sockIntegration`](docs/API.md#sockintegration) option to match what you're using.

For each of the integrations listed above,
you can also take a look at the corresponding [sample projects](https://github.com/pmmmwh/react-refresh-webpack-plugin/tree/main/examples) for a better understanding of how things should be wired up.

## API

Please refer to [the API docs](docs/API.md) for all available options.

## FAQs and Troubleshooting

Please refer to [the Troubleshooting guide](docs/TROUBLESHOOTING.md) for FAQs and resolutions to common issues.

## License

This project is licensed under the terms of the [MIT License](/LICENSE).

## Related Work

- [Initial Implementation by @maisano](https://gist.github.com/maisano/441a4bc6b2954205803d68deac04a716)
