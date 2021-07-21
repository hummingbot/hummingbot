# gatsby-remark-code-titles

[![CircleCI](https://circleci.com/gh/DSchau/gatsby-remark-code-titles.svg?style=svg)](https://circleci.com/gh/DSchau/gatsby-remark-code-titles)

Adds a code title to code snippets

![Code title example](./example/code-title.png)

## Install

```bash
npm install gatsby-remark-code-titles --save-dev
```

## How to use

in your gatsby-config.js

```js
plugins: [
  {
    resolve: 'gatsby-transformer-remark',
    options: {
      plugins: [
        {
          resolve: 'gatsby-remark-code-titles',
          options: {
            className: 'your-custom-class-name',
          },
        }, // IMPORTANT: this must be ahead of other plugins that use code blocks
      ],
    },
  },
];
```

### Include CSS

Now that we've injected the custom title, we need to style it! This presumes standard Gatsby prism highlighting, but tweak to your heart's content.

```css
.gatsby-remark-code-title {
  margin-bottom: -0.6rem;
  padding: 0.5em 1em;
  font-family: Consolas, 'Andale Mono WT', 'Andale Mono', 'Lucida Console',
    'Lucida Sans Typewriter', 'DejaVu Sans Mono', 'Bitstream Vera Sans Mono',
    'Liberation Mono', 'Nimbus Mono L', Monaco, 'Courier New', Courier,
    monospace;

  background-color: black;
  color: white;
  z-index: 0;

  border-top-left-radius: 0.3em;
  border-top-right-radius: 0.3em;
}
```

### Usage in Markdown

in your Markdown content

````
```js:title=example-file.js
alert('how cool is this!');
```js
````

This plugin will parse the Markdown AST, pluck the title, and then "clean" the code snippet language for further processing. In other words, the plugin will create the following structure, injecting a custom `div` with the title:

````
<div class="gatsby-code-title">example-file.js</div>
```js
alert('how cool is this');
```
````
