# Migration guide

To move one of our old Hexo-based sites to Gatsby using this theme, you can follow these steps:

## 1. Clean house

First, clone the repo and move into the _docs_ directory (`cd docs`). Delete that directory's _package-lock.json_ file and *node_modules* directory, and edit the _package.json_ file to look like this:

```json
{
  "scripts": {
    "start": "gatsby develop --prefix-paths"
  }
}
```

Change the name of the _public_ directory (this typically contains the *_redirects* Netlify file) to _static_.

```bash
mv public static
```

You'll also need to edit the _docs_ directory's _.gitignore_ to reflect this change. You'll want to ignore the entire _public_ directory, as well as the _.cache_ directory. These changes will typically look like this:

```
  public/*
- !public/_redirects
+ .cache
```

## 2. Install dependencies

```bash
$ npm install gatsby gatsby-theme-apollo-docs
```

That was easy!

## 3. Port _config.yml to gatsby-config.js

All of this theme's [configuration options](#configuration) are represented in existing Hexo *_config.yml* files. Moving them over is just a matter of copying and pasting, modifying some property names, and changing snake_case names to camelCase ones. In addition, you must add a `root` option and set it to `__dirname`. For example, here's a before/after of the iOS docs configs:

*_config.yml*

```yaml
title: Apollo iOS Guide # called `subtitle` in gatsby-config.js
subtitle: Apollo iOS Guide # not needed
description: A guide to using Apollo with iOS
versions:
  - '1' # if there's only one version, you don't need to port this option
sidebar_categories:
  null:
    - index
    - installation
    - api-reference
  Usage:
    - downloading-schema
    - initialization
    - fetching-queries
    - fragments
    - watching-queries
    - mutations
github_repo: apollographql/apollo-ios
root: /docs/ios/ # called `pathPrefix` in gatsby-config.js
content_root: docs/source # not required, but called `contentDir` in gatsby-config.js
url: https://www.apollographql.com/docs/ios/ # not needed
public_dir: public/docs/ios # not needed
```

_gatsby-config.js_

```js
const themeOptions = require('gatsby-theme-apollo-docs/theme-options');

module.exports = {
  pathPrefix: '/docs/ios', // similar to `root` in _config.yml
  plugins: [
    {
      resolve: 'gatsby-theme-apollo-docs',
      options: {
        ...themeOptions, // spread the default Apollo theme options
        root: __dirname, // this is the only new property added
        subtitle: 'Apollo iOS Guide',
        description: 'A guide to using Apollo with iOS',
        githubRepo: 'apollographql/apollo-ios',
        sidebarCategories: {
          null: [
            'index',
            'installation',
            'api-reference'
          ],
          Usage:[
            'downloading-schema',
            'initialization',
            'fetching-queries',
            'fragments',
            'watching-queries',
            'mutations',
          ]
        }
      }
    }
  ]
};
```

## 4. Add a Netlify config

Add a _netlify.toml_ file to the repo root. It should contain `base`, `publish`, and `command` properties. The `base` and `publish` properties should always be `docs/` and `docs/public/`, respectively. The `command` property will build the site using the `gatsby build` command, and then move the built website into the appropriate directory to be served using our [website router](https://github.com/apollographql/website-router/blob/master/_redirects). You should edit the directory names in that property to reflect the `pathPrefix` option that you provided in your _gatsby-config.js_ file. Here's an example of the iOS docs Netlify config:

```toml
[build]
  base    = "docs/"
  publish = "docs/public/"
  command = "gatsby build --prefix-paths && mkdir -p docs/ios && mv public/* docs/ios && mv docs public/ && mv public/docs/ios/_redirects public"
[build.environment]
  NPM_VERSION = "6"
```

## 5. Deploy

When these changes are pushed to GitHub and a pull request is opened, Netlify will build a deploy preview so you can check out the changes made. When you open the deploy preview in your web browser, be sure to append the `pathPrefix` to the URL. In the example of the iOS docs, the URL would look like this: https://deploy-preview-471--apollo-ios-docs.netlify.com/docs/ios
