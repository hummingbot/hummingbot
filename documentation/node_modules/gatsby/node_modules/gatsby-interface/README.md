<img src="https://user-images.githubusercontent.com/21834/74070062-35b91980-4a00-11ea-93a8-b77bde7b4c37.png" width="48" height="48" alt="rebeccapurple dot" />
<br>
<br>

# Gatsby Interface

<a href="https://www.npmjs.org/package/gatsby-interface">
  <img src="https://img.shields.io/npm/v/gatsby-interface.svg" alt="Current npm package version." />
</a>
<a href="https://npmcharts.com/compare/gatsby-interface?minimal=true">
  <img src="https://img.shields.io/npm/dm/gatsby-interface.svg" alt="Downloads per month on npm." />
</a>
<a href="https://npmcharts.com/compare/gatsby-interface?minimal=true">
  <img src="https://img.shields.io/npm/dt/gatsby-interface.svg" alt="Total downloads on npm." />
</a>

Storybook available at [gatsby-interface.netlify.com](https://gatsby-interface.netlify.com/):

![screenshot](https://user-images.githubusercontent.com/21834/78464072-36f78180-76e5-11ea-96dc-5e4911dee1f4.png)

## Installation

Using [npm](https://www.npmjs.com/):

```shell
npm install gatsby-interface --save
```

Using [Yarn](https://yarnpkg.com/):

```shell
yarn add gatsby-interface
```

### Fonts

Certain Gatsby Interface components require the `Futura PT` webfont. These files are git-ignored to prevent the unauthorized release of licensed assets, and are not included in this repository.

Gatsby Inc. employees can download these fonts from our [Google Drive](https://drive.google.com/drive/u/1/folders/1DA_iNzLbd1_gvU_FWTzYK6MgLSl85L4v). Put all those folders in `src/assets/futura-pt` and you should be good to go!

## Development

1. Clone the repository: `git clone https://github.com/gatsby-inc/gatsby-interface.git`.
2. Install dependencies: `yarn`.
3. Run Storybook: `yarn storybook`.

### Adding a new component

If you want to add a new component to `gatsby-interface`, run `yarn scaffold:component` to create stubs:

```bash
yarn scaffold:component MyNewComponent
```

This script will do the following:

- Create a `MyNewComponent` directory for the component at [`./src/components`](./src/components)
- Generate a file for the component itself, `MyNewComponent.tsx`, with stubs for props type, styles and even some variants
- Generate a story file, `MyNewComponent.stories.tsx`, which follows the suggestions from [Component Checklist proposal](https://github.com/gatsby-inc/gatsby-interface/issues/205).
- Generate an index file, `index.ts`, which reexports everything from the component file
- Add export statements to library index files: [`./src/index.ts`](./src/index.ts) and [`./index-ts-only.ts`](./index-ts-only.ts).

Everything that is generated should be working out of the box and be ready to shipped (though please avoid shipping the stubs 😅)

### Contributing

These are some patterns and best practices we use when contributing to `gatsby-interface`:

- Use React hooks and functional components: https://reactjs.org/docs/hooks-intro.html.
- Use CSS props for styling: https://emotion.sh/docs/css-prop.
- Use `gatsby-design-tokens` for styling constants: https://www.gatsbyjs.org/guidelines/design-tokens/.
- Use compound components to make components more composable and flexible: https://kentcdodds.com/blog/compound-components-with-react-hooks.
- Make all PRs against the `dev` branch.
- Use `TONE` and `VARIANT` prop (when appropriate) to definie color style and variant of a component — see e. g. `<Button>`.
- Make the component as generic as possible so it can be used _anywhere_ by _anything_.
- Components in the `skeletons` folder provide only the functionality, but no styles, and can be used within other components.
- Write Storybook stories for any component created: https://storybook.js.org/docs/basics/writing-stories/.
- Typscript coming soon!
- Unit tests coming soon!

### Chromatic testing

To run the visual testing tool, run `CHROMATIC_APP_CODE=<insert_app_code> yarn chromatic`

You can find the app code in the Chromatic dashboard - https://www.chromaticqa.com

## ❗ Code of Conduct

Gatsby is dedicated to building a welcoming, diverse, safe community. We expect everyone participating in the Gatsby community to abide by our [**Code of Conduct**](https://gatsbyjs.org/contributing/code-of-conduct/). Please read it. Please follow it. In the Gatsby community, we work hard to build each other up and create amazing things together. 💪💜
