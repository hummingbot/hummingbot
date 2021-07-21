# gatsby-remark-check-links

[![Build Status](https://github.com/trevorblades/gatsby-remark-check-links/workflows/Node%20CI/badge.svg)](https://github.com/trevorblades/gatsby-remark-check-links/actions)

A [Gatbsy Remark](https://www.gatsbyjs.org/packages/gatsby-transformer-remark/) plugin that detects broken links to pages and headings among your website's markdown pages. This is useful if your page slugs or heading IDs are being automatically generated. Heading IDs might be created by [`gatsby-remark-autolink-headers`](https://www.gatsbyjs.org/packages/gatsby-remark-autolink-headers/), for example.

It will provide output about the broken links in the terminal when your site builds and as you make changes to pages. In production, your build will break if there are any broken links.

- [Installation](#installation)
- [Usage](#usage)
- [Options](#options)
  - [`ignore`](#ignore)
  - [`exceptions`](#exceptions)
  - [`verbose`](#verbose)
- [Caveats](#caveats)
- [License](#license)

## Installation

```bash
$ npm install gatsby-remark-check-links
```

## Usage

Add the plugin to your `gatsby-transformer-remark` options or the `remarkPlugins` key in the `gatsby-plugin-mdx` options, if you're using that.

```js
// gatsby-config.js
module.exports = {
  plugins: [
    {
      resolve: 'gatsby-transformer-remark',
      options: {
        plugins: [
          'gatsby-remark-autolink-headers',
          'gatsby-remark-check-links'
        ]
      }
    }
  ]
};
```

If broken links are found, you will see feedback in the console. If you stop seeing console output, you might need to [clear your cache](#caveats). The link checker console output should look something like this:

```
3 broken links found on /examples/react/
- /foo/bar/
- /intro/#some-hash
- /intro/#some-other-hash
⠀
2 broken links found on /intro/
- /foo/baz/
- /examples/ract/
⠀
5 broken links found
```

## Options

If you need to disable link checking for certain pages, you can supply options to the plugin. There are two options: `ignore` and `exceptions`, and while they both expect an array of paths, they work differently.

```js
// gatsby-config.js
module.exports = {
  plugins: [
    {
      resolve: 'gatsby-transformer-remark',
      options: {
        plugins: [
          'gatsby-remark-autolink-headers',
          {
            resolve: 'gatsby-remark-check-links',
            options: {
              ignore: [
                '/foo/bar',
                '/generated/docs/'
              ],
              exceptions: [
                '/bar/baz/',
                '/dynamic/headings/'
              ]
            }
          }
        ]
      }
    }
  ]
};
```

### `ignore`

Paths passed to `ignore` will **not** have their content checked for broken links. This is useful if you have auto-generated pages where you're certain the links work, but it would be a nusance to correct their formatting every time a new set of pages is generated.

### `exceptions`

Paths passed to `exceptions` will ensure that any links from other pages to these paths or hashes within them will **not** count as broken. This is useful if the linked page is created programatically, or if the final rendered version of a markdown page contains headings that aren't available during the MDAST-transforming stage of the build (it could be using some fancy MDX component, for example.)

### `verbose`

Disable logs and warnings in your console by passing `false` to the `verbose` option, which is `true` by default.

## Caveats

Once a markdown page has been cached by Gatsby, you won't see any output about its broken links until the file changes or your cache gets cleared. If you want to see link check output for *all* files every time you run `npm start`, you can set up a `prestart` npm script that removes your Gatsby cache directory:

```json
{
  "scripts": {
    "prestart": "gatsby clean"
  }
}
```

## License

[MIT](./LICENSE)
