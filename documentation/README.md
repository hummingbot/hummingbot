# Hummingbot Client Documentation

This repository is documentation for the [Hummingbot](https://hummingbot.io) trading bot client, whose github repo can be found [here](https://github.com/coinalpha/hummingbot).

The **deployed** version of this documentation is available at:

- https://docs.hummingbot.io/

## gatsby-theme-apollo-docs

This site uses [gatsby-theme-apollo-docs](https://github.com/apollographql/gatsby-theme-apollo/tree/master/packages/gatsby-theme-apollo-docs).

1. Install required dependencies

### Setup

#### `.env`

If you are going to build and update site indexing for Algolia, you will need to save the `env-template` file as `.env` locally and populate the variable values. Currently, we only use environment values for Algolia search.

#### node

Node versions this repo has been successfully been run and tested with: 10.22.1, 12.19.0

### Running

- `yarn install` to install dependencies
- `yarn start` to launch local server
- Open a browser to the link provided in the console

## Deploy previews

Each pull request will be built and available for preview on netlify. To access the preview, look for the link in the status checks of the pull request.

1. Push changes to your branch
2. Create a pull request
3. Click **Details** next to "**deploy/netlify** Deploy preview ready!" from the pull request

## Deployment

This site uses [Algolia search](https://algolia.com) which requires the environment variables from `env-template`.

## Troubleshooting

Gatsby and react often results in conflicts. If you have errors running `npm start` or `gatsby develop`:

- you may need to try to uninstall and reinstall `react`, `react-dom`, and `gatsby` ([reference](https://github.com/gatsbyjs/gatsby/issues/19827#issuecomment-573986378))
- you can also try `yarn install` instead of `npm install`

## Contributions

When contributing, please review the [contributing guidelines](https://docs.hummingbot.io/developer/contributing/)

## Component Guides

When editing markdown pages, please review the list of available components in [Component Guide](https://docs.hummingbot.io/app-guide/component-guide/)

**Note**: Use `master` as base branch
