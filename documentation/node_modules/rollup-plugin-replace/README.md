# rollup-plugin-replace
[![](https://img.shields.io/npm/v/rollup-plugin-replace.svg?style=flat)](https://www.npmjs.com/package/rollup-plugin-replace)

Replace strings in files while bundling them.


## Installation

```bash
npm install --save-dev rollup-plugin-replace
```


## Usage

Generally, you need to ensure that rollup-plugin-replace goes *before* other things (like rollup-plugin-commonjs) in your `plugins` array, so that those plugins can apply any optimisations such as dead code removal.


```js
// rollup.config.js
import replace from 'rollup-plugin-replace';

export default {
  // ...
  plugins: [
    replace({
      ENVIRONMENT: JSON.stringify('production')
    })
  ]
};
```


## Options

```js
{
  // a minimatch pattern, or array of patterns, of files that
  // should be processed by this plugin (if omitted, all files
  // are included by default)...
  include: 'config.js',

  // ...and those that shouldn't, if `include` is otherwise
  // too permissive
  exclude: 'node_modules/**',

  // To replace every occurrence of `<@foo@>` instead of every
  // occurrence of `foo`, supply delimiters
  delimiters: ['<@', '@>'],

  // All other options are treated as `string: replacement`
  // replacers...
  VERSION: '1.0.0',
  ENVIRONMENT: JSON.stringify('development'),

  // or `string: (id) => replacement` functions...
  __dirname: (id) => `'${path.dirname(id)}'`,

  // ...unless you want to be careful about separating
  // values from other options, in which case you can:
  values: {
    VERSION: '1.0.0',
    ENVIRONMENT: JSON.stringify('development')
  }
}
```


## Word boundaries

By default, values will only match if they are surrounded by *word boundaries* — i.e. with options like this...

```js
{
  changed: 'replaced'
}
```

...and code like this...

```js
console.log('changed');
console.log('unchanged');
```

...the result will be this:

```js
console.log('replaced');
console.log('unchanged');
```

If that's not what you want, specify empty strings as delimiters:

```js
{
  changed: 'replaced',
  delimiters: ['', '']
}
```



## License

MIT
