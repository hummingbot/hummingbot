# hummingbot-docs
The official documentation for Hummingbot

## Installation

This documentation site uses the [MkDocs](https://www.mkdocs.org/) documentation-focused static site engine, along with the [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/) theme.

### Material for MkDocs Insiders

The deployed site at https://docs.hummingbot.io uses the Insiders build of Material for MkDocs, which features experimental features like tags and social cards. 

For internal Hummingbot staff, see below for how to deploy the site in your local development environment and Netlify:

#### Local

```
# change to conda base environment since there may be conflicts with hummingbot environment
➜ conda activate

# install mkdocs-material-insiders and dependencies
(base) ➜ pip install git+ssh://git@github.com/CoinAlpha/mkdocs-material-insiders

# install revision date plugin
(base) ➜ pip install mkdocs-git-revision-date-plugin
```

#### Netlify

The `netlify.toml` file in the root directory contains the instructions used by Netlify to build the site. Make sure to add the `GH_TOKEN` as a build environment variable in Netlify beforehand.

If you push your commits to the `docs/staging` branch, Netlify will automatically deploy that branch to a staging site.

## Develop

From the `/documentation`, directory, run the following command to build Markdown files into HTML and start a development server to browse the documentation:
```
mkdocs serve
```

Afterwards, go to `http://localhost:8000` in your web browser.

## Build

After editing, run the following command to build the documentation for deployment:

```
mkdocs build
```

## Contributions

We welcome contributions by our community! 

Please create a new [issue](https://github.com/CoinAlpha/hummingbot/issues) if there are areas of the documentation you would like us to improve, or submit a [pull request](https://github.com/CoinAlpha/hummingbot/pulls) with the proposed change!