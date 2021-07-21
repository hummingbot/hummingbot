# slugify [![Build Status](https://travis-ci.org/sindresorhus/slugify.svg?branch=master)](https://travis-ci.org/sindresorhus/slugify)

> Slugify a string

Useful for URLs, filenames, and IDs.

It correctly handles [German umlauts](https://en.wikipedia.org/wiki/Germanic_umlaut), Vietnamese, Arabic, Russian, Romanian, Turkish and more.


## Install

```
$ npm install @sindresorhus/slugify
```


## Usage

```js
const slugify = require('@sindresorhus/slugify');

slugify('I ♥ Dogs');
//=> 'i-love-dogs'

slugify('  Déjà Vu!  ');
//=> 'deja-vu'

slugify('fooBar 123 $#%');
//=> 'foo-bar-123'

slugify('I ♥ 🦄 & 🐶', {
	customReplacements: [
		['🐶', 'dog']
	]
});
//=> 'i-love-unicorn-and-dog'
```

## API

### slugify(input, [options])

#### input

Type: `string`

#### options

Type: `Object`

##### separator

Type: `string`<br>
Default: `-`

```js
const slugify = require('@sindresorhus/slugify');

slugify('BAR and baz');
//=> 'bar-and-baz'

slugify('BAR and baz', {separator: '_'});
//=> 'bar_and_baz'
```

##### lowercase

Type: `boolean`<br>
Default: `true`

Make the slug lowercase.

```js
const slugify = require('@sindresorhus/slugify');

slugify('Déjà Vu!');
//=> 'deja-vu'

slugify('Déjà Vu!', {lowercase: false});
//=> 'Deja-Vu'
```

##### decamelize

Type: `boolean`<br>
Default: `true`

Convert camelcase to separate words. Internally it does `fooBar` → `foo bar`.

```js
const slugify = require('@sindresorhus/slugify');

slugify('fooBar');
//=> 'foo-bar'

slugify('fooBar', {decamelize: false});
//=> 'foobar'
```

##### customReplacements

Type: `Array<string[]>`<br>
Default: `[
	['&', ' and '],
	['🦄', ' unicorn '],
	['♥', ' love ']
]`

Specifying this only replaces the default if you set an item with the same key, like `&`. The replacements are run on the original string before any other transformations.

```js
const slugify = require('@sindresorhus/slugify');

slugify('Foo@unicorn', {
	customReplacements: [
		['@', 'at']
	]
});
//=> 'fooatunicorn'
```

Add a leading and trailing space to the replacement to have it separated by dashes:

```js
const slugify = require('@sindresorhus/slugify');

slugify('foo@unicorn', {
	customReplacements: [
		['@', ' at ']
	]
});
//=> 'foo-at-unicorn'
```


## Related

- [slugify-cli](https://github.com/sindresorhus/slugify-cli) - CLI for this module
- [filenamify](https://github.com/sindresorhus/filenamify) - Convert a string to a valid safe filename


## License

MIT © [Sindre Sorhus](https://sindresorhus.com)
