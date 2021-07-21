# gatsby-theme-apollo-core

This is the base theme for building Apollo-branded Gatsby sites. It contains a small amount of configuration, and a handful of components that make it easy to build consistent-looking UIs.

It comes with a few Gatsby plugins:

 - `gatsby-plugin-svgr` enables [importing SVGs as React components](https://www.gatsbyjs.org/packages/gatsby-plugin-svgr)
 - `gatsby-plugin-emotion` server renders your [Emotion](https://emotion.sh) styles
 - `gatsby-plugin-react-helmet` server renders `<head>` tags set with [React Helmet](https://github.com/nfl/react-helmet)
 - `gatsby-plugin-typography` provides a stylesheet reset and sets default styles for basic HTML elements

- [Installation](#installation)
- [Configuration](#configuration)
- [Components and utilities](#components-and-utilities)
  - [`Layout`](#layout)
  - [`Sidebar`](#sidebar)
  - [`SidebarNav`](#sidebarnav)
  - [`ResponsiveSidebar`](#responsivesidebar)
  - [`Logo`](#logo)
  - [Colors](#colors)
  - [Breakpoints](#breakpoints)
- [Deploying to a subdirectory](#deploying-to-a-subdirectory)
- [Examples](#examples)
- [License](#license)

## Installation

```bash
$ npm install gatsby gatsby-theme-apollo-core
```

## Configuration

```js
// gatsby-config.js
module.exports = {
  plugins: ['gatsby-theme-apollo-core'],
  siteMetadata: {
    title: 'Apollo rocks!',
    description: 'Gatsby themes are pretty cool too...'
  }
};
```

## Components and utilities

All of the React components and utilities documented here are available as named exports in the `gatsby-theme-apollo-core` package. You can import them like this:

```js
import {MenuButton, Sidebar, breakpoints} from 'gatsby-theme-apollo-core';
```

### `Layout`

`Layout` should wrap every page that gets created. It configures [React Helmet](https://github.com/nfl/react-helmet) and sets the meta description tag with data from the `siteMetadata` property in your Gatsby config.

```js
import {Layout} from 'gatsby-theme-apollo-core';

function MyPage() {
  return (
    <Layout>
      Hello world
    </Layout>
  );
}
```

| Prop name | Type | Required |
| --------- | ---- | -------- |
| children  | node | yes      |

### `Sidebar`

A component that renders a sidebar with a [`LogoTitle`](#logo-title) component in the top left corner. It can also be configured to collapse into the left side of the page on narrow windows.

```js
import {Layout, Sidebar} from 'gatbsy-theme-apollo';

function MyPage() {
  return (
    <Layout>
      <Sidebar>
        Sidebar content goes here
      </Sidebar>
    </Layout>
  );
}
```

| Prop name  | Type   | Required | Description                                                                      |
| ---------- | ------ | -------- | -------------------------------------------------------------------------------- |
| children   | node   | yes      |                                                                                  |
| responsive | bool   | no       | If `true`, the sidebar will behave as a drawer absolutely positioned on the left |
| open       | bool   | no       | Controls the sidebar visibility when the `responsive` prop is `true`             |
| logoLink   | string | no       | The URL/path that the sidebar logo should link to                                |

### `SidebarNav`

A configurable two-tiered, expandable/collapsible navigation component for use in conjunction with the `Sidebar` component above. It accepts a `contents` prop that defines what links and collapsible sections get rendered. Here's an example of the expected shape of a `contents` prop:

```js
const contents = [
  {
    title: 'Getting started',
    path: '/'
  },
  {
    title: 'External link',
    path: 'https://apollographql.com',
    anchor: true
  },
  {
    title: 'Advanced features',
    pages: [
      {
        title: 'Schema stitching',
        path: '/advanced/schema-stitching'
      }
    ]
  }
];
```

Each element in the array can have `title`, `path`, `pages`, and `anchor` props. `pages` is an array of more elements with the same shape. By default, a [Gatsby `Link` component](https://www.gatsbyjs.org/docs/gatsby-link/) will be used to render the links, but you can use a regular HTML anchor tag (`<a>`) by passing the `anchor` property to `true` on any page object.

The `SidebarNav` component gives the currently selected page an "active" style, and if it's a subpage, it will keep the currently active section expanded. To facilitate this, you must pass the current path to the `pathname` prop. Luckily, Gatsby exposes this in the `location` prop that gets passed automatically to every page!

```js
import {Layout, Sidebar, SidebarNav} from 'gatsby-theme-apollo-core';

function MyPage(props) {
  return (
    <Layout>
      <Sidebar>
        <SidebarNav
          contents={contents}
          pathname={props.location.pathname}
        />
      </Sidebar>
    </Layout>
  );
}
```

| Prop name      | Type   | Required | Description                                                       |
| -------------- | ------ | -------- | ----------------------------------------------------------------- |
| contents       | array  | yes      | An array of items to render                                       |
| pathname       | string | yes      | The current path (`props.location.pathname` expected)             |
| alwaysExpanded | bool   | no       | If `true`, all collapsible sections are expanded and cannot close |


### `ResponsiveSidebar`

A render props component that manages the state for responsive sidebars. On mobile devices, the sidebar is opened by a `MenuButton` component, and dismissed when the user clicks away from the sidebar. This component's `children` prop accepts a function that provides values and functions to enable this behavior easily.

```js
import {
  Layout,
  Sidebar,
  ResponsiveSidebar,
  FlexWrapper,
  MenuButton
} from 'gatsby-theme-apollo-core';

function MyPage() {
  return (
    <Layout>
      <ResponsiveSidebar>
        {({sidebarOpen, openSidebar, onWrapperClick, sidebarRef}) => (
          <FlexWrapper onClick={onWrapperClick}>
            <Sidebar responsive open={sidebarOpen} ref={sidebarRef}>
              This is a sidebar
            </Sidebar>
            <MenuButton onClick={openSidebar} />
          </FlexWrapper>
        )}
      </ResponsiveSidebar>
    </Layout>
  );
}
```

| Prop name | Type | Required | Description                                                 |
| --------- | ---- | -------- | ----------------------------------------------------------- |
| children  | func | yes      | A render prop-style function that returns a React component |

### `Logo`

A component that renders the Apollo logo. This logo can be removed or replaced using component shadowing.

```js
import {Logo} from 'gatsby-theme-apollo-core';

function MyPage() {
  return <Logo />;
}
```

#### Customizing the logo

Through [component shadowing](https://www.gatsbyjs.org/blog/2019-01-29-themes-update-child-theming-and-component-shadowing/), you can override the logo that gets shown. Simply create a file that exports a SVG React component in your theme consumer at _src/gatsby-theme-apollo-core/components/logo.js_.

```js
// src/gatsby-theme-apollo-core/components/logo.js
export {ReactComponent as default} from '../../assets/custom-logo.svg';
```

Check out [this CodeSandbox link](https://codesandbox.io/s/mq7p0z3wmj) for a full component shadowing example.

[![Edit Component shadowing example](https://codesandbox.io/static/img/play-codesandbox.svg)](https://codesandbox.io/s/mq7p0z3wmj?fontsize=14)

| Prop name | Type | Required | Description                          |
| --------- | ---- | -------- | ------------------------------------ |
| noLogo    | bool | no       | If `true`, the Apollo logo is hidden |

### Colors

An object mapping semantic names to hex strings. All of these colors are drawn from [Space Kit](https://space-kit.netlify.com/?path=/story/color--brand-colors). You can use this utility to write CSS-in-JS rules like this:

```js
import {colors} from 'gatsby-theme-apollo-core';

const StyledButton = styled.button({
  color: colors.primary,
  background: colors.background
});
```

#### Customizing colors

You can override the default color palette using shadowing. The only constraint is that the `primary` and `secondary` palette keys must be [colors from Space Kit](https://github.com/apollographql/space-kit#colors). Here's an example of a shadowed color palette:

```js
// src/gatsby-theme-apollo-core/utils/colors.js
const {colors} = require('gatsby-theme-apollo-core/src/utils/colors');
const {colors: spaceKitColors} = require('@apollo/space-kit/colors');

exports.colors = {
  ...colors,
  primary: spaceKitColors.red.base,
  divider: '#aeaeae'
};
```

You can refer to the [default colors file](./src/utils/colors.js) for palette keys that can be customized.

 ### Breakpoints

 A mapping of size keys to media queries. This is useful for writing responsive CSS-in-JS components.

 ```js
 import {breakpoints} from 'gatsby-theme-apollo-core';

 const StyledMenu = styled.nav({
   fontSize: 24,
   [breakpoints.lg]: {
     fontSize: 20
   },
   [breakpoints.md]: {
     fontSize: 16
   },
   [breakpoints.sm]: {
     fontSize: 12
   }
 })
 ```

| Key | Value                      |
| --- | -------------------------- |
| sm  | @media (max-width: 600px)  |
| md  | @media (max-width: 850px)  |
| lg  | @media (max-width: 1120px) |

## Deploying to a subdirectory

In order to deploy a Gatsby site to a subdirectory, there are a few extra steps to take. First, you must provide a `pathPrefix` property in your Gatsby config. This option combined with the `--prefix-paths` option in the Gatsby CLI will handle most of the hard work. Read more about path prefixing in Gatsby [here](https://www.gatsbyjs.org/docs/path-prefix/).

```js
// gatsby-config.js
module.exports = {
  ...
  pathPrefix: '/YOUR_PATH_PREFIX'
};
```

Now, when you run `npx gatsby bulid --prefix-paths`, all pages, references to static assets, and links between pages will be prefixed with your custom path. That means that if you made a page with the path _/about_, it will live at _/**YOUR_PATH_PREFIX**/about_. In order for this to work within our server configuration, your website files also must exist in a directory with the same name. Here's how this sequence of events would look if you ran commands in your terminal:

```bash
$ npx gatsby build --prefix-paths
$ mkdir -p YOUR_PATH_PREFIX
$ mv public/* YOUR_PATH_PREFIX
$ mv YOUR_PATH_PREFIX public/
```

We use [Netlify](https://netlify.com) to deploy our websites, so to express this slightly more complicated build process to them, create a _netlify.toml_ file that follows this pattern:

```toml
# netlify.toml
[build]
  base = "/"
  publish = "public/"
  command = "gatsby build --prefix-paths && mkdir -p YOUR_PATH_PREFIX && mv public/* YOUR_PATH_PREFIX && mv YOUR_PATH_PREFIX public/"
```

We use [Netlify redirects](https://docs.netlify.com/routing/redirects/#syntax-for-the-redirects-file) to manage our server rewrites and redirects. To point your new Netlify deployment to a page on apollographql.com, add a rule to our [website router `_redirects` file](https://github.com/apollographql/website-router/blob/master/_redirects#L57-L59). It should look something like this:

```
/YOUR_PATH_PREFIX/* YOUR_NETLIFY_URL/YOUR_PATH_PREFIX/:splat 200!
```

## Examples

- [Principled GraphQL](https://github.com/apollographql/principled-graphql)

## License

[MIT](../../LICENSE)
