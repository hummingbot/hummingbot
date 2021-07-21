<div align="center">
  <img height="100" src="https://i.imgur.com/YPhoQOA.png">
  <h1 align="center">Space Kit</h1>
  <p>The home base for Apollo's design system, Space Kit provides essential design resources for our developers to use in the Apollo-branded interfaces that they create.</p>
  <a href="https://www.npmjs.com/package/@apollo/space-kit" title="@apollo/space-kit npm page">
    <img src="https://img.shields.io/npm/v/@apollo/space-kit.svg">
  </a>
</div>

## Table of Contents <!-- omit in toc -->

- [Installation](#installation)
- [Usage](#usage)
- [Exports](#exports)
  - [Stylesheet reset](#stylesheet-reset)
  - [Colors](#colors)
  - [Icons](#icons)
  - [Typography](#typography)
  - [Buttons](#buttons)
  - [Modals](#modals)
  - [Loaders](#loaders)
  - [Emotion Example](#emotion-example)
- [Developing Space Kit](#developing-space-kit)
  - [`npm link`](#npm-link)
  - [Tests](#tests)
  - [Releases](#releases)
  - [Icons](#icons-1)
  - [TypeScript](#typescript)
  - [Storybook](#storybook)
  - [Beta Releases](#beta-releases)
- [Resources](#resources)

## Installation

```shell
npm install @apollo/space-kit
```

## Usage

Import things into your JS app from the `@apollo/space-kit` package. All available exports are documented [here](#exports).

```js
import "@apollo/space-kit/reset.css"; // import this at app root
import { colors } from "@apollo/space-kit";

function MyComponent() {
  return (
    <button
      style={{
        backgroundColor: colors.indigo.dark,
        color: "white",
        border: `1px solid ${colors.grey.light}`,
      }}
    >
      ...
    </button>
  );
}
```

## Exports

### Stylesheet reset

A "base" stylesheet with a few sensible rules. It uses [normalize.css](https://necolas.github.io/normalize.css/) to smooth out any inconsistencies between the ways that different browsers render elements. It also applies `box-sizing: border-box;` to everything, for [a better element sizing experience](https://www.paulirish.com/2012/box-sizing-border-box-ftw/). Lastly, the stylesheet imports and sets our two main font families: [Source Sans Pro](https://fonts.google.com/specimen/Source+Sans+Pro), and [Source Code Pro](https://fonts.google.com/specimen/Source+Code+Pro).

You'll probably want to include this file once in your app, ideally at the top-most level. For instance, in a Gatsby site that would be your [`layout.js` component](https://www.gatsbyjs.org/docs/layout-components/).

**JS + webpack or similar**

```js
import "@apollo/space-kit/reset.css";
```

**LESS**

```less
@import (inline) "../node_modules/@apollo/space-kit/reset.css
```

### Colors

A JavaScript object that maps color names to palettes of hex codes to apply on-brand color to elements on a page. The available colors include:

- `pink`
- `teal`
- `indigo`
- `black`
- `grey`
- `silver`
- `red`
- `green`
- `blue`
- `orange`
- `yellow`
- `purple`

When you access a color by name (i.e. `colors.indigo`), you'll find a palette of hex codes keyed by a "lightness" variant. These include:

- `base`
- `dark`
- `darker`
- `darkest` (not on `black`, `grey`, or `silver`)
- `light`
- `lighter`
- `lightest` (not on `black`, `grey`, or `silver`)

**CSS-in-JS**

```jsx
import styled from "@emotion/styled";
import { colors } from "@apollo/space-kit";

const StyledButton = styled.button({
  backgroundColor: colors.indigo.dark,
  color: "white",
  border: `1px solid ${colors.grey.light}`,
});

function MyComponent() {
  return (
    <div>
      <StyledButton>Save</StyledButton>
      <StyledButton
        style={{
          backgroundColor: colors.red.base,
        }}
      >
        Delete
      </StyledButton>
    </div>
  );
}
```

### Icons

All our icons are displayed in a gallery in [Storybook](https://space-kit.netlify.com/?path=/story/space-kit--icons).

Note that there are no styles or classes applied to the SVGs by default; you'll have to add a `width` and `height` to see the icons; and apply a text color to color them.

All our icons are SVG files stored in [`./icons/src/svgs`](./icons/src/svgs). There are scripts set up to convert these SVGs into React components, and then to transpile those files for consumption. These conversions and transpilations are `.gitignore`'ed, so they are not maintained in source control.

These icons are _not_ open source and are only licensed for use in this project. See [license](./icons/LICENSE.md) for more details.

Please see [#developing-space-kit-icons](#icons-1) for instructions on adding new icons.

### Typography

Zeplin: https://zpl.io/V4ep7Jy

We decided to export our typography style system as plain old JavaScript to allow consumers to chose how to implement the configurations. The names relate to each other and do not imply intent. For example, we did not use the names "title" or "caption" because the style system only gives the options; it's up to each consumer to chose a style guide.

To consume these types with [Tailwindcss](https://tailwindcss.com/), one would create a plugin to add a [utility](https://v0.tailwindcss.com/docs/plugins#adding-utilities) to add these classnames.

This example will use the original names prefixed with `space-kit-`:

```js
const typographyConfig = require("@apollo/space-kit/typography");

module.exports = {
  plugins: [
    function spaceKitTypography({ addUtilities }) {
      addUtilities(
        Object.entries(typographyConfig.base).reduce(
          (accumulator, [name, properties]) => ({
            ...accumulator,
            [`.space-kit-${name}`]: properties,
          }),
          {}
        )
      );
    },
  ],
};
```

You could also use the style system to add intent:

```js
const typographyConfig = require("@apollo/space-kit/typography");

module.exports = {
  plugins: [
    function spaceKitTypography({ addUtilities }) {
      addUtilities({
        ".space-kit-title": typographyConfig.base.xxxlarge,
        ".caption": typographyConfig.base.xsmall,
      });
    },
  ],
};
```

#### Example

```js
import React from "react";
import { IconServices } from "@apollo/space-kit/icons/IconServices";

export const IconServiceItem: React.FC = () => (
  <div className="w-5 h-5">
    <IconServices className="w-full h-full text-teal" />
  </div>
);
```

### Buttons

Zeplin: https://zpl.io/amdN6Pr

This is our style system for buttons. This is intended to be used to create your project's style guide. Configure the color by passing an optional `color` prop with a value from the space kit palette. You should use emotion or tailwind to set the text color as this will not be handled for you unless you're using a flat button.

You can use this component with no configuration as-is to use the default colors.

You can configure anything you'd like with tailwind or emotion, but you should never have to do this.

#### Tailwind Example

```js
import React from "react";
import classnames from "classnames";
import { Button } from "@apollo/space-kit/Button";
import { colors } from "@apollo/space-kit/colors";

export const PrimaryButton: React.FC<ComponentProps<typeof Button>> = ({
  children,
  className,
  ...otherProps
}) => (
  <Button
    {...otherProps}
    color={colors.blue.base}
    className={classnames(className, "text-white")}
  >
    {children}
  </Button>
);
```

#### Emotion Example

```js
/** @jsx jsx */
import React from "react";
import { Button } from "@apollo/space-kit/Button";
import { colors } from "@apollo/space-kit/colors";
import { jsx } from "@emotion/core";

export const PrimaryButton: React.FC<ComponentProps<typeof Button>> = ({
  children,
  ...otherProps
}) => (
  <Button
    {...otherProps}
    color={colors.indigo.dark}
    css={{
      color: "white",
    }}
  >
    {children}
  </Button>
);
```

### Modals

### Loaders

Zeplin: https://app.zeplin.io/project/5c7dcb5ab4e654bca8cde54d/screen/5d56d40acf2df541b112fc57

#### Spinners

Spinners are used when we are unable to determine loading time. Ideally, they should appear as briefly and infrequently as possible.

Spinners can be configured through their `theme` and `size` props. By default a loading spinner will have a 'light' theme and 'medium' size.

You can configure anything you'd like with tailwind or emotion, but you should never have to do this.

#### Example

```js
import React from "react";
import { LoadingSpinner } from "@apollo/space-kit/Loaders";

export const LoadingPage: React.FC<Props> = (otherProps) => (
  <div {...otherProps} >
    <LoadingSpinner
      theme="light"
      size="medium"
    />
  </div>
);
```

### Emotion Example

```js
/** @jsx jsx */
import React from "react";
import { Modal } from "@apollo/space-kit/Modal";
import { Button } from "@apollo/space-kit/Button";
import { colors } from "@apollo/space-kit/colors";
import { jsx } from "@emotion/core";

export const SmallModal: React.FC<ComponentProps<typeof Modal>> = ({
  children, 
  ...otherProps 
}) => (
    <Modal
    {...otherProps}
      size="small"
      title="Are you sure you want to remove Jeremy?"
      primaryAction={
        <Button
          color={colors.red.base}
          css={{ color: colors.white }}
          type="button"
        >
          Yes, remove
        </Button>
      }
    >
      Jeremy will no longer have access to the MGD-Private. You can always add
      them back to the organization later.
    </Modal>
);
```

#### FAQ

##### My icons aren't showing up in the UI

Make sure that the icon component has a width and height applied to it. That can mean applying classes or styles directly to the Icon component, or setting the component to have `height: 100%` and `width: 100%` and then applying a size to the containing element.

##### Why can't I import from `IconServices` from `@apollo/space-kit/icons`?

My goal was to minimze the bundle size increase caused by using these icons. If I had named exports from `space-kit/icons`, then the user would have to make sure they are tree-shaking to only import the icons they are actually using. `engine-frontend` is _not_ yet tree-shaking, so we decided to not make the imports an option.

##### Why does each icon have a named export instead of a default export?

The engine-frontend team and Apollo OSS teams have decided to not use default exports; this continues that trend.

## Developing Space Kit

Developing locally against Storybook is easy; run `npm run storybook`.

### `npm link`

You can use `npm link` to develop Space Kit features directly inside another project with a little bit of work. `npm link` does not work out of the box, however, because of React hooks. We must use the same instance of `React` both in this project and in your consuming project, so you must use the following process or you will get errors about react hooks:

* Link the consuming package's react package into space kit
    
    Run the following from the space kit directory:

    ```shell
    npm link ../engine-frontend/node_modules/react
    ```

* Use development build of space kit

    Run `npm run watch` and everything should build automatically

    Note: When developing a new feature of space-kit, please make sure that the `watch` script will automatically perform all setps necessary to build for development. For example, there is a `watch:typescript` script and a `watch:npmwatch` script that will watch all TypeScript files and watch all the svg icons for changes.

* Link space kit

    Run the following from the space kit directory:

    ```shell
    npm link
    ```

    Then run the following form the consuming package's directory:

    ```shell
    npm link @apollo/space-kit
    ```

### Tests

We use `jest` and `testing-library` for unit/integration tests and will soon use [Chromatic](https://www.chromaticqa.com/) for visual regression testing.

#### Integration Tests

The hardest part about writing tests is knowing what should be tested and what shouldn't. Test interactions: test whatever you'd  test by hand that would give you release confidence.

A few dos and don'ts:

- DO: Test interactions
- DON'T: test anything that doesn't give you more confidence

    In other words, _do not_ add tests to increase code-coverage.

- DO: [Write test names that explain what is being tested, what input is being given, and what is expected](https://github.com/goldbergyoni/javascript-testing-best-practices#-%EF%B8%8F-11-include-3-parts-in-each-test-name)
- DO: [Write simple tests with no abstractions](https://github.com/goldbergyoni/javascript-testing-best-practices#%EF%B8%8F-0-the-golden-rule-design-for-lean-testing)

Some resources on testing:

- [JavaScript Testing Best Practices](https://github.com/goldbergyoni/javascript-testing-best-practices)
- https://kentcdodds.com/blog/
    - [Avoid nesting when you're testing](https://kentcdodds.com/blog/avoid-nesting-when-youre-testing)
    - [Write fewer, longer tests](https://kentcdodds.com/blog/write-fewer-longer-tests)

### Releases

Releases are handled automatically after merging PRs by [`intuit/auto`](https://github.com/intuit/auto). You can split PRs into a feature branch and then send that as a PR to master; that'll use all the different PRs to create the changelog.

#### Semver

Each PR needs to have a SemVer lable in GitHub so `auto` knows how to . Available labels are:

* `patch` - Increment the patch version when merged
* `minor` - Increment the minor version when merged
* `major` - Increment the major version when merged
* `prerelease` - Create a pre-release version when merged
* `skip-release` - Preserve the current version when merged
* `internal` - Changes only affect the internal API
* `documentation` - Changes only affect the documentation

Use `skip-release` if you don't want an automatic release with your PR.

There is a CircleCI job that checks that an appropriate label is on the PR. It will always fail initially. GitHub actions are set up to re-run the CI check when labels are added or removed. it can be found in [`.github/main.workflow`](./.github/main.workflow).

#### Changelog

The changelog will be updated automatically with the title of your PR used as the line item in the changelog. The sections of the changelog will decided by the labels you gave your PR. If you want to add more information for the changelog, add a `## Release Notes` section in your PR description. https://intuit.github.io/auto/pages/auto-changelog.html#additional-release-notes

### Icons

Our icons are all stored in [`icons/src/svgs`](./icons/src/svgs) in folders named for the icon category. To add new icons, add svg files to one of these category folders and open a pull request. Fill and stroke colors with values `#000` or `#000000` will be replace by `currentColor` to allow the consumer to change the colors; all other colors will be maintained and will not be configurable.

All React components will be automatically generated and the TypeScript will be transpiled automatically after merging to `master`.

The following scripts are available:

- `icons:clean`: Clean all the React components and TypeScript generated files from the `icons/` directory. This will not touch the raw svg files in `icons/src`.
- `icons:generate`: Generate TypeScript files for each icon. These will be immediately available in Storybook.
- `icons`: Run `icons:clean` and `icons:genreate` in series
- `build:typescript`: Transpile TypeScript files to be consumed externally.
- `watch`: Watch TypeScript files and automatically update.

  This is useful when you've `npm link`'ed this repository and are developing against another project.

### TypeScript

To watch all TypeScript projects for development, run the `npm run watch` script.

### Storybook

Many elements of Space Kit are showcased in Storybook, which can be used for local development by running:

```
npm install
npm run storybook
```

All pull requests will automatically generate deploy previews and the `master` branch is automatically deployed to https://space-kit.netlify.com.

[![Netlify Status](https://api.netlify.com/api/v1/badges/d5469491-a3d2-4ee1-b31d-d7f87ae806f8/deploy-status)](https://app.netlify.com/sites/space-kit/deploys)

### Beta Releases

While local development should be done with [`npm link`](https://docs.npmjs.com/cli/link),sometimes we need to release pre-release versions. This will require you use `npm version` to bump the package (prepatch, preminor, or premajor would be a smart move). Then you can use `npm publish --tag=next` (or whatever tag you want to use).

## Resources

- [Space Kit's style guide (Zeplin)](https://app.zeplin.io/project/5c7dcb5ab4e654bca8cde54d/screen/5cd0c46bce9a42346c709328)
- [Engine's style guide (Storybook)](https://storybook.apollographql.com)
