    # contentful-management.js

> JavaScript SDK for [Contentful's](https://www.contentful.com) Content Management API.

[![npm](https://img.shields.io/npm/v/contentful-management.svg)](https://www.npmjs.com/package/contentful-management)
[![Build Status](https://travis-ci.org/contentful/contentful-management.js.svg?branch=master)](https://travis-ci.org/contentful/contentful-management.js)
[![codecov](https://codecov.io/gh/contentful/contentful-management.js/branch/master/graph/badge.svg)](https://codecov.io/gh/contentful/contentful-management.js)
[![Dependency Status](https://david-dm.org/contentful/contentful-management.js.svg)](https://david-dm.org/contentful/contentful-management.js)
[![devDependency Status](https://david-dm.org/contentful/contentful-management.js/dev-status.svg)](https://david-dm.org/contentful/contentful-management.js#info=devDependencies)

[![semantic-release](https://img.shields.io/badge/%20%20%F0%9F%93%A6%F0%9F%9A%80-semantic--release-e10079.svg)](https://github.com/semantic-release/semantic-release)
[![js-standard-style](https://img.shields.io/badge/code%20style-standard-brightgreen.svg)](http://standardjs.com/)
[![npm downloads](https://img.shields.io/npm/dm/contentful-management.svg)](http://npm-stat.com/charts.html?package=contentful-management)
[![gzip bundle size](http://img.badgesize.io/https://unpkg.com/contentful-management/dist/contentful-management.browser.min.js?compression=gzip)](https://unpkg.com/contentful-management/dist/contentful-management.browser.min.js)

[Contentful](https://www.contentful.com) provides a content infrastructure for digital teams to power content in websites, apps, and devices. Unlike a CMS, Contentful was built to integrate with the modern software stack. It offers a central hub for structured content, powerful management and delivery APIs, and a customizable web app that enable developers and content creators to ship digital products faster.

## Features

- Content management and retrieval through Contentful's [Content Management API](https://www.contentful.com/developers/docs/references/content-management-api/).
- Built in rate limiting with recovery procedures
- Asset processing helpers

## Supported environments

Browsers and Node.js:

- Chrome
- Firefox
- Edge
- Safari
- node.js (LTS)
- IE11 (with [legacy version](#legacy-browsers) of the library)

Other browsers should also work, but at the moment we're only running automated tests on the browsers and Node.js versions specified above.

# Getting started

To get started with the Contentful Management JS SDK you'll need to install it, and then get credentials which will allow you to access your content in Contentful.

- [Installation](#installation)
- [Authentication](#authentication)
- [Using ES6 import](#using-es6-import)
- [Your first request](#your-first-request)
- [Troubleshooting](#troubleshooting)
- [Documentation/References](#documentationreferences)

## Installation

### Node:

Using [npm](http://npmjs.org):

```sh
npm install contentful-management
```

Using [yarn](https://yarnpkg.com/lang/en/):

```sh
yarn add contentful-management
```

### Browser:

For browsers, we recommend to download the SDK via npm or yarn to ensure 100% availability.

If you'd like to use a standalone built file you can use the following script tag or download it from [jsDelivr](https://www.jsdelivr.com/package/npm/contentful-management), under the `dist` directory:

```html
<script src="https://cdn.jsdelivr.net/npm/contentful-management@latest/dist/contentful-management.browser.min.js"></script>
```

**It's not recommended to use the above URL for production.**

Using `contentful@latest` will always get you the latest version, but you can also specify a specific version number:

```html
<!-- Avoid using the following url for production. You can not rely on its availability. -->
<script src="https://cdn.jsdelivr.net/npm/contentful-management@4.0.1/dist/contentful-management.browser.min.js"></script>
```

The Contentful Management SDK will be accessible via the `contentfulManagement` global variable.

Check the [releases](https://github.com/contentful/contentful-management.js/releases) page to know which versions are available.

### Typings

This library also comes with typings to use with typescript.

### Legacy browsers:

This library also comes with a legacy version to support Internet Explorer 11 and other older browsers. It already contains a polyfill for Promises.

To support legacy browsers in your application, use `contentful-management.legacy.min.js` instead of `contentful-management.browser.min.js`

## Authentication

To get content from Contentful, an app should authenticate with an OAuth bearer token.

If you want to use this SDK for a simple tool or a local app that you won't redistribute or make available to other users, you can get an API key for the Management API at our [Authentication page](https://www.contentful.com/developers/docs/references/authentication/).

If you'd like to create an app which would make use of this SDK but that would be available for other users, where they could authenticate with their own Contentful credentials, make sure to also check out the section about [Creating an OAuth Application](https://www.contentful.com/developers/docs/references/authentication/#creating-an-oauth-20-application)

## Using ES6 import

You can use the es6 import with the SDK as follow

```js
// import createClient directly
import { createClient } from 'contentful-management'
var client = createClient({
  // This is the access token for this space. Normally you get the token in the Contentful web app
  accessToken: 'YOUR_ACCESS_TOKEN',
})
//....
```

OR

```js
// import everything from contentful
import * as contentful from 'contentful-management'
var client = contentful.createClient({
  // This is the access token for this space. Normally you get the token in the Contentful web app
  accessToken: 'YOUR_ACCESS_TOKEN',
})
// ....
```

## Your first request

The following code snippet is the most basic one you can use to get content from Contentful with this SDK:

```js
var contentful = require('contentful-management')
var client = contentful.createClient({
  // This is the access token for this space. Normally you get the token in the Contentful web app
  accessToken: 'YOUR_ACCESS_TOKEN',
})

// This API call will request a space with the specified ID
client.getSpace('spaceId').then((space) => {
  // Now that we have a space, we can get entries from that space
  space.getEntries().then((entries) => {
    console.log(entries.items)
  })

  // let's get a content type
  space.getContentType('product').then((contentType) => {
    // and now let's update its name
    contentType.name = 'New Product'
    contentType.update().then((updatedContentType) => {
      console.log('Update was successful')
    })
  })
})
```

You can try and change the above example at [Tonic](https://tonicdev.com/npm/contentful-management).

## Troubleshooting

- **I can't Install the package via npm** - Check your internet connection - It is called `contentful-management` and not `contenful-management` ¯\\\_(ツ)\_/¯
- **Can I use the SDK in react native projects** - Yes it is possible
- **I get the error: Unable to resolve module `http`** - Our SDK is supplied as node and browser version. Most non-node environments, like React Native, act like a browser. To force using of the browser version, you can require it via: `const { createClient } = require('contentful-management/dist/contentful-management.browser.min.js')`
- **I am not sure what payload to send when creating and entity (Asset/Entity/ContentType etc...)** - Check the Content Management API [docs](https://www.contentful.com/developers/docs/references/content-management-api/) or the examples in the reference [docs](https://contentful.github.io/contentful-management.js) - Feel free to open an issue if you didn't find what you need in the above links
- 😱 **something is wrong what should I do** - If it is a bug related to the code create a GitHub issue and make sure to remove any credential for your code before sharing it. - If you need to share your credentials, for example you have an issue with your space, please create a support ticket. - Please **do not** share your management token in a GitHub issue

## Documentation/References

To help you get the most out of this SDK, we've prepared reference documentation, tutorials and other examples that will help you learn and understand how to use this library.

### Configuration

The `createClient` method supports several options you may set to achieve the expected behavior:

```js
contentful.createClient({
  ... your config here ...
})
```

#### accessToken (required)

Your CMA access token.

#### host (default: `'api.contentful.com'`)

Set the host used to build the request URI's.

#### hostUpload (default: `'upload.contentful.com'`)

Set the host used to build the upload related request uri's.

#### basePath (default: ``)

This path gets appended to the host to allow request urls like `https://gateway.example.com/contentful/` for custom gateways/proxies.

#### httpAgent (default: `undefined`)

Custom agent to perform HTTP requests. Find further information in the [axios request config documentation](https://github.com/mzabriskie/axios#request-config).

#### httpsAgent (default: `undefined`)

Custom agent to perform HTTPS requests. Find further information in the [axios request config documentation](https://github.com/mzabriskie/axios#request-config).

#### headers (default: `{}`)

Additional headers to attach to the requests. We add/overwrite the following headers:

- Content-Type: `application/vnd.contentful.management.v1+json`
- X-Contentful-User-Agent: `sdk contentful-management.js/1.2.3; platform node.js/1.2.3; os macOS/1.2.3`
  (Automatically generated)

#### proxy (default: `undefined`)

Axios proxy configuration. See the [axios request config documentation](https://github.com/mzabriskie/axios#request-config) for further information about the supported values.

#### retryOnError (default: `true`)

By default, this SDK is retrying requests which resulted in a 500 server error and 429 rate limit response. Set this to `false` to disable this behavior.

#### logHandler (default: `function (level, data) {}`)

Errors and warnings will be logged by default to the node or browser console. Pass your own log handler to intercept here and handle errors, warnings and info on your own.

#### requestLogger (default: `function (config) {}`)

Interceptor called on every request. Takes Axios request config as an arg. Default does nothing. Pass your own function to log any desired data.

#### responseLogger (default: `function (response) {}`)

Interceptor called on every response. Takes Axios response object as an arg. Default does nothing. Pass your own function to log any desired data.

### Reference documentation

The [Contentful's JS SDK reference](https://contentful.github.io/contentful-management.js) documents what objects and methods are exposed by this library, what arguments they expect and what kind of data is returned.

Most methods also have examples which show you how to use them.

You can start by looking at the top level `contentfulManagement` namespace.

The `ContentfulClientAPI` namespace defines the methods at the Client level which allow you to create and get spaces.

The `ContentfulSpaceAPI` namespace defines the methods at the Space level which allow you to create and get entries, assets, content types and other possible entities.

The `Entry`, `Asset` and `ContentType` namespaces show you the instance methods you can use on each of these entities, once you retrieve them from the server.

> From version 1.0.0 onwards, you can access documentation for a specific version by visiting `https://contentful.github.io/contentful-management.js/contentful-management/<VERSION>`

### Contentful JavaScript resources

Read the [Contentful for JavaScript](https://www.contentful.com/developers/docs/javascript/) page for Tutorials, Demo Apps, and more information on other ways of using JavaScript with Contentful

### REST API reference

This library is a wrapper around our Contentful Management REST API. Some more specific details such as search parameters and pagination are better explained on the [REST API reference](https://www.contentful.com/developers/docs/references/content-management-api/), and you can also get a better understanding of how the requests look under the hood.

### Legacy contentful-management.js

For versions prior to 1.0.0, you can access documentation at [https://github.com/contentful/contentful-management.js/tree/legacy](https://github.com/contentful/contentful.js/tree/legacy)

## Versioning

This project strictly follows [Semantic Versioning](http://semver.org/) by use of [semantic-release](https://github.com/semantic-release/semantic-release).

This means that new versions are released automatically as fixes, features or breaking changes are released.

You can check the changelog on the [releases](https://github.com/contentful/contentful-management.js/releases) page.

## Migration from contentful-management.js 3.x

The bundle for browsers is now called `contentful-management.browser.min.js` to mark it clearly as browser only bundle. If you need to support IE 11 or other old browsers, you may use the `contentful-management.legacy.min.js`. Node will automatically use the `contentful-management.node.min.js` while bundlers like Webpack will resolve to the new ES-modules version of the library.

No changes to the API of the library were made.

## Migration from contentful-management.js 1.x and older

contentful.js 1.x was a major rewrite, with some API changes. While the base functionality remains the same, some method names have changed, as well as some internal behaviors.

See the [migration guide](MIGRATION.md) for more information.

## Support

If you have a problem with this library, please file an [issue](https://github.com/contentful/contentful-management.js/issues/new) here on GitHub.

If you have other problems with Contentful not related to this library, you can contact [Customer Support](https://support.contentful.com).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md)

## License

MIT
