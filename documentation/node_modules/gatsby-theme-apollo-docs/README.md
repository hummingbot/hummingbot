# gatsby-theme-apollo-docs

This is an entirely configuration-based Gatsby theme that generates a documentation website based on a series of Markdown or MDX files. It also exports a series of [components](#components) that can be used within MDX pages.

- [Installation](#installation)
- [Configuration](#configuration)
- [Options](#options)
  - [`versions`](#versions)
  - [`sidebarCategories`](#sidebarcategories)
  - [`navConfig`](#navconfig)
  - [Algolia configuration](#algolia-configuration)
- [Creating pages](#creating-pages)
- [Component shadowing](#component-shadowing)
- [Components](#components)
  - [`ExpansionPanel`](#expansionpanel)
  - [`ExpansionPanelList`](#expansionpanellist)
  - [`ExpansionPanelListItem`](#expansionpanellistitem)
  - [`MultiCodeBlock`](#multicodeblock)
- [Deployment](#deployment)
- [Migration](#migration)
- [Examples](#examples)
- [License](#license)

## Installation

If you're using this package, you'll also need to install `gatsby` and its peer dependencies, `react` and `react-dom`. Next, install the theme:

```bash
$ npm install gatsby-theme-apollo-docs
```

## Configuration

You can configure `gatsby-theme-apollo-docs` for use with any set of docs using the provided configuration options. You may also use [component shadowing](../gatsby-theme-apollo-core#customizing-the-logo) to customize elements like the logo or color scheme.

```js
// gatsby-config.js
module.exports = {
  pathPrefix: '/docs/apollo-server',
  plugins: [
    {
      resolve: 'gatsby-theme-apollo-docs',
      options: {
        root: __dirname,
        subtitle: 'Apollo Server',
        description: 'A guide to using Apollo Server',
        githubRepo: 'apollographql/apollo-server',
        defaultVersion: '2',
        versions: {
          '1': 'version-1'
        },
        sidebarCategories: {
          null: [
            'index',
            'getting-started',
            'whats-new'
          ],
          Features: [
            'features/mocking',
            'features/errors',
            'features/data-sources'
          ]
        }
      }
    }
  ]
};
```

## Options

| Option name         | Type   | Required | Description                                                                                                                             |
| ------------------- | ------ | -------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| root                | string | Yes      | Must be `__dirname`                                                                                                                     |
| siteName            | string | Yes      | The main title for the website, used in the `<title>` element and top left corner of the site                                           |
| description         | string | Yes      | The site description for SEO and social (FB, Twitter) tags                                                                              |
| sidebarCategories   | object | Yes      | An object mapping categories to page paths (see [`sidebarCategories` reference](#sidebarcategories))                                    |
| subtitle            | string | No       | The page title that gets rendered above the sidebar navigation                                                                          |
| pageTitle           | string | No       | The string to be rendered in the page's `<title>` tag. If omitted, `siteName` will be used.                                             |
| baseDir             | string | No       | If your Gatsby site does not live in the root of your project directory/git repo, pass the subdirectory name here (`docs`, for example) |
| contentDir          | string | No       | The directory where docs content exists (`content` by default)                                                                          |
| githubHost          | string | No       | The hostname of the GitHub server (`github.com` by default)                                                                             |
| githubRepo          | string | No       | The owner and name of the content repository on GitHub                                                                                  |
| spectrumPath        | string | No       | The path to be appended to Spectrum links                                                                                               |
| gaTrackingId        | string | No       | Your site's Google Analytics tracking ID                                                                                                |
| algoliaApiKey       | string | No       | Your [Algolia DocSearch](https://community.algolia.com/docsearch/) API key                                                              |
| algoliaIndexName    | string | No       | The name of your DocSearch index                                                                                                        |
| baseUrl             | string | No       | The origin where your website will be hosted (e.g. `https://www.apollographql.com`)                                                     |
| spectrumHandle      | string | No       | Your Spectrum community's handle/slug                                                                                                   |
| twitterHandle       | string | No       | Your Twitter handle, without the "@"                                                                                                    |
| youtubeUrl          | string | No       | The URL of your YouTube channel                                                                                                         |
| defaultVersion      | string | No       | An identifier for the default selected version, served at the root of the docset (/)                                                    |
| localVersion        | string | No       | If the local files represent a version different from the `defaultVersion`, specify an identifier for the local version here            |
| versions            | array  | No       | An array of objects representing the versions that the website should generate                                                          |
| navConfig           | object | No       | An object defining the top-left navigation links (see [`navConfig` reference](#navconfig))                                              |
| checkLinksOptions   | object | No       | Options accepted by [`gastby-remark-check-links`](https://github.com/trevorblades/gatsby-remark-check-links#options)                    |
| ignore              | array  | No       | Files to ignore using [anymatch](https://github.com/es128/anymatch)-compatible definition pattern                                       |
| gatsbyRemarkPlugins | array  | No       | Additional Gatsby Remark plugins to pass to `gatsby-transformer-remark` and `gatsby-plugin-mdx`                                         |
| remarkPlugins       | array  | No       | Additional [Remark plugins](https://www.gatsbyjs.org/packages/gatsby-plugin-mdx/#remark-plugins) to pass to `gatsby-plugin-mdx`         |

### `versions`

If omitted, only one version of docs will be built, based on the files in the theme consumer repository. If provided, the `versions` option expects an object mapping older versions' labels to their respective git branch. The current filesystem will still determine the "default" version. The default label for this version is "Latest", but is configurable by the `defaultVersion` option.

```js
defaultVersion: '2.5',
versions: {
  '2.4': 'version-2.4'
}
```

### `sidebarCategories`

The `sidebarCategories` option is an object keyed by category titles. Each entry in the object is an array of page paths. The path should resemble the location of a Markdown/MDX file in the git repository, relative to `contentDir`, and without the _.md_ extension. Sidebar navigation items that are **not** a member of a category live under the `null` key. To add an external link to your sidebar, your can provide a string formatted like a Markdown link.

```js
{
  null: [
    'index',
    'getting-started',
    'whats-new'
  ],
  Features: [
    'features/mocking',
    'features/errors',
    'features/data-sources'
  ],
  'External links': [
    '[Principled GraphQL](https://principledgraphql.com/)'
  ]
}
```

### `navConfig`

The `navConfig` option should be an object keyed by link titles. The values should be objects with `description`, and `url` properties. Check out the [default theme options](./theme-options.js) for an example of the expected shape of this data.

### Algolia configuration

This theme allows you to use Algolia DocSearch to power a search bar in the site. You'll need to provide your API key and index name to the theme in the form of `algoliaApiKey` and `algoliaIndexName` options.

To get these, [sign up with DocSearch](https://docsearch.algolia.com/apply/) for an open source repo. You'll be able to configure your indexing strategy by submitting a PR to edit your config file in [the `docsearch-configs` repo](https://github.com/algolia/docsearch-configs).

## Creating pages

This theme generates pages based on Markdown or MDX files in the [`contentDir`](#configuration) directory of a repo. Your Markdown/MDX files should contain some frontmatter defining their titles and descriptions.

```yaml
---
title: Introduction
description: What is Apollo Server and what does it do?
---

Apollo Server is the best way to quickly build a production-ready, self-documenting API for GraphQL clients, using data from any source.
```

Page URLs will be derived from the file paths of your Markdown. You can nest Markdown files within directories to create pages with additional path segments. You can overwrite this default path by adding a `slug` field to your Markdown frontmatter header.

## Component shadowing

You can customize a website using this theme further by taking advantage of [component shadowing](../gatsby-theme-apollo-core#customizing-the-logo).

By default, this theme sets the website favicon to [the one from Apollo's website](https://www.apollographql.com/favicon.ico) within its [internal `SEO` component](../gatsby-theme-apollo-core/src/components/seo.js). If you wanted to use your own favicon, you could shadow the `SEO` component within your site and add your custom SEO/favicon implementation.

```js
// src/gatsby-theme-apollo-docs/components/seo.js
import React from 'react';
import {Helmet} from 'react-helmet';

export default function SEO({title, description, siteName}) {
  return (
    <Helmet>
      <link rel="icon" href="/path/to/custom-favicon.ico" />
      {/* other SEO tags (OpenGraph, Twitter, etc.) */}
    </Helmet>
  );
}
```

## Components

This theme exports React components that you can use in MDX files throughout a documentation website.

### `ExpansionPanel`

An expandable panel of content used to hide complex information or instructions that might be a tangent from the main topic of the content it lives within.

| Prop     | Type   | Description                                                        |
| -------- | ------ | ------------------------------------------------------------------ |
| children | node   | The content of the panel, usually includes an `ExpansionPanelList` |
| title    | string | The title of the panel, visible even when the panel is closed      |

### `ExpansionPanelList`

A wrapper element that should be used in conjunction with [`ExpansionPanelListItem`](#expansionpanellistitem) components. It renders an `li` element with some styles baked in.

### `ExpansionPanelListItem`

A list item for use with the `ExpansionPanelList`. It comes with a cicular area to its left to render a number, glyph, or some way to indicate progress through a set of instructions. You can write Markdown within these elements if you keep everything detabbed and add an empty line between your content and the component's opening and closing tags.

| Prop     | Type   | Description                                                                            |
| -------- | ------ | -------------------------------------------------------------------------------------- |
| children | node   | The content of the list item, usually a block of Markdown                              |
| number   | string | The number displayed to the left of the list item, or a checkmark if "check" is passed |

```js
import {
  ExpansionPanel,
  ExpansionPanelList,
  ExpansionPanelListItem
} from 'gatsby-theme-apollo-docs';

<ExpansionPanel title="How to use the ExpansionPanel component">

Add a line break _between_ JSX tags and content to parse the content as *Markdown*

<ExpansionPanelList>
<ExpansionPanelListItem number="1">

<h4>h4 works well as a heading here</h4>

- markdown
- works
- here

</ExpansionPanelListItem>
<ExpansionPanelListItem number="check">

<h4>That's it!</h4>

> MDX is super fun

</ExpansionPanelListItem>
</ExpansionPanelList>

</ExpansionPanel>
```

### `MultiCodeBlock`

Wraps adjacent code blocks to allow users to toggle between them using a dropdown menu.

````js
import {MultiCodeBlock} from 'gatsby-theme-apollo-docs';

<MultiCodeBlock>

```js
// a JavaScript code block
```

```ts
// a TypeScript code block
```

</MultiCodeBlock>
````

## Deployment

All docs sites will eventually be deployed into a subdirectory, as configured by the `pathPrefix` option&mdash;/docs/apollo-server, for example. [Read this guide](../gatsby-theme-apollo-core/#deploying-to-a-subdirectory) to learn more about publishing to a subdirectory.

## Migration

To migrate an older Hexo site to this theme, [follow this guide](MIGRATION.md).

## Examples

- [Apollo](https://www.apollographql.com/docs)
- [WPGraphQL](https://docs.wpgraphql.com)
- [Analytics](https://getanalytics.io)
- [Sigmetic](https://docs.sigmetic.io)
- [LoginRadius](https://www.loginradius.com/docs/developer/)

Are you using this theme in your own project? Submit a PR with your website added to this list!

## License

[MIT](../../LICENSE)
