export interface ParseOptions {
	/**
	Decode the keys and values. URI components are decoded with [`decode-uri-component`](https://github.com/SamVerschueren/decode-uri-component).

	@default true
	*/
	readonly decode?: boolean;

	/**
	@default 'none'

	- `bracket`: Parse arrays with bracket representation:

		```
		import queryString = require('query-string');

		queryString.parse('foo[]=1&foo[]=2&foo[]=3', {arrayFormat: 'bracket'});
		//=> {foo: ['1', '2', '3']}
		```

	- `index`: Parse arrays with index representation:

		```
		import queryString = require('query-string');

		queryString.parse('foo[0]=1&foo[1]=2&foo[3]=3', {arrayFormat: 'index'});
		//=> {foo: ['1', '2', '3']}
		```

	- `comma`: Parse arrays with elements separated by comma:

		```
		import queryString = require('query-string');

		queryString.parse('foo=1,2,3', {arrayFormat: 'comma'});
		//=> {foo: ['1', '2', '3']}
		```

	- `separator`: Parse arrays with elements separated by a custom character:

		```
		import queryString = require('query-string');

		queryString.parse('foo=1|2|3', {arrayFormat: 'separator', arrayFormatSeparator: '|'});
		//=> {foo: ['1', '2', '3']}
		```

	- `none`: Parse arrays with elements using duplicate keys:

		```
		import queryString = require('query-string');

		queryString.parse('foo=1&foo=2&foo=3');
		//=> {foo: ['1', '2', '3']}
		```
	*/
	readonly arrayFormat?: 'bracket' | 'index' | 'comma' | 'separator' | 'none';

	/**
	The character used to separate array elements when using `{arrayFormat: 'separator'}`.

	@default ,
	*/
	readonly arrayFormatSeparator?: string;

	/**
	Supports both `Function` as a custom sorting function or `false` to disable sorting.

	If omitted, keys are sorted using `Array#sort`, which means, converting them to strings and comparing strings in Unicode code point order.

	@default true

	@example
	```
	import queryString = require('query-string');

	const order = ['c', 'a', 'b'];

	queryString.parse('?a=one&b=two&c=three', {
		sort: (itemLeft, itemRight) => order.indexOf(itemLeft) - order.indexOf(itemRight)
	});
	//=> {c: 'three', a: 'one', b: 'two'}
	```

	@example
	```
	import queryString = require('query-string');

	queryString.parse('?a=one&c=three&b=two', {sort: false});
	//=> {a: 'one', c: 'three', b: 'two'}
	```
	*/
	readonly sort?: ((itemLeft: string, itemRight: string) => number) | false;

	/**
	Parse the value as a number type instead of string type if it's a number.

	@default false

	@example
	```
	import queryString = require('query-string');

	queryString.parse('foo=1', {parseNumbers: true});
	//=> {foo: 1}
	```
	*/
	readonly parseNumbers?: boolean;

	/**
	Parse the value as a boolean type instead of string type if it's a boolean.

	@default false

	@example
	```
	import queryString = require('query-string');

	queryString.parse('foo=true', {parseBooleans: true});
	//=> {foo: true}
	```
	*/
	readonly parseBooleans?: boolean;

	/**
	Parse the fragment identifier from the URL and add it to result object.

	@default false

	@example
	```
	import queryString = require('query-string');

	queryString.parseUrl('https://foo.bar?foo=bar#xyz', {parseFragmentIdentifier: true});
	//=> {url: 'https://foo.bar', query: {foo: 'bar'}, fragmentIdentifier: 'xyz'}
	```
	*/
	readonly parseFragmentIdentifier?: boolean;
}

export interface ParsedQuery<T = string> {
	[key: string]: T | T[] | null;
}

/**
Parse a query string into an object. Leading `?` or `#` are ignored, so you can pass `location.search` or `location.hash` directly.

The returned object is created with [`Object.create(null)`](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Object/create) and thus does not have a `prototype`.

@param query - The query string to parse.
*/
export function parse(query: string, options: {parseBooleans: true, parseNumbers: true} & ParseOptions): ParsedQuery<string | boolean | number>;
export function parse(query: string, options: {parseBooleans: true} & ParseOptions): ParsedQuery<string | boolean>;
export function parse(query: string, options: {parseNumbers: true} & ParseOptions): ParsedQuery<string | number>;
export function parse(query: string, options?: ParseOptions): ParsedQuery;

export interface ParsedUrl {
	readonly url: string;
	readonly query: ParsedQuery;

	/**
	The fragment identifier of the URL.

	Present when the `parseFragmentIdentifier` option is `true`.
	*/
	readonly fragmentIdentifier?: string;
}

/**
Extract the URL and the query string as an object.

If the `parseFragmentIdentifier` option is `true`, the object will also contain a `fragmentIdentifier` property.

@param url - The URL to parse.

@example
```
import queryString = require('query-string');

queryString.parseUrl('https://foo.bar?foo=bar');
//=> {url: 'https://foo.bar', query: {foo: 'bar'}}

queryString.parseUrl('https://foo.bar?foo=bar#xyz', {parseFragmentIdentifier: true});
//=> {url: 'https://foo.bar', query: {foo: 'bar'}, fragmentIdentifier: 'xyz'}
```
*/
export function parseUrl(url: string, options?: ParseOptions): ParsedUrl;

export interface StringifyOptions {
	/**
	Strictly encode URI components with [`strict-uri-encode`](https://github.com/kevva/strict-uri-encode). It uses [`encodeURIComponent`](https://developer.mozilla.org/en/docs/Web/JavaScript/Reference/Global_Objects/encodeURIComponent) if set to `false`. You probably [don't care](https://github.com/sindresorhus/query-string/issues/42) about this option.

	@default true
	*/
	readonly strict?: boolean;

	/**
	[URL encode](https://developer.mozilla.org/en/docs/Web/JavaScript/Reference/Global_Objects/encodeURIComponent) the keys and values.

	@default true
	*/
	readonly encode?: boolean;

	/**
	@default 'none'

	- `bracket`: Serialize arrays using bracket representation:

		```
		import queryString = require('query-string');

		queryString.stringify({foo: [1, 2, 3]}, {arrayFormat: 'bracket'});
		//=> 'foo[]=1&foo[]=2&foo[]=3'
		```

	- `index`: Serialize arrays using index representation:

		```
		import queryString = require('query-string');

		queryString.stringify({foo: [1, 2, 3]}, {arrayFormat: 'index'});
		//=> 'foo[0]=1&foo[1]=2&foo[2]=3'
		```

	- `comma`: Serialize arrays by separating elements with comma:

		```
		import queryString = require('query-string');

		queryString.stringify({foo: [1, 2, 3]}, {arrayFormat: 'comma'});
		//=> 'foo=1,2,3'
		```

  - `separator`: Serialize arrays by separating elements with character:

		```
		import queryString = require('query-string');

		queryString.stringify({foo: [1, 2, 3]}, {arrayFormat: 'separator', arrayFormatSeparator: '|'});
		//=> 'foo=1|2|3'
		```

	- `none`: Serialize arrays by using duplicate keys:

		```
		import queryString = require('query-string');

		queryString.stringify({foo: [1, 2, 3]});
		//=> 'foo=1&foo=2&foo=3'
		```
	*/
	readonly arrayFormat?: 'bracket' | 'index' | 'comma' | 'separator' | 'none';

	/**
	The character used to separate array elements when using `{arrayFormat: 'separator'}`.

	@default ,
	*/
	readonly arrayFormatSeparator?: string;

	/**
	Supports both `Function` as a custom sorting function or `false` to disable sorting.

	If omitted, keys are sorted using `Array#sort`, which means, converting them to strings and comparing strings in Unicode code point order.

	@default true

	@example
	```
	import queryString = require('query-string');

	const order = ['c', 'a', 'b'];

	queryString.stringify({a: 1, b: 2, c: 3}, {
		sort: (itemLeft, itemRight) => order.indexOf(itemLeft) - order.indexOf(itemRight)
	});
	//=> 'c=3&a=1&b=2'
	```

	@example
	```
	import queryString = require('query-string');

	queryString.stringify({b: 1, c: 2, a: 3}, {sort: false});
	//=> 'b=1&c=2&a=3'
	```
	*/
	readonly sort?: ((itemLeft: string, itemRight: string) => number) | false;

	/**
	Skip keys with `null` as the value.

	Note that keys with `undefined` as the value are always skipped.

	@default false

	@example
	```
	import queryString = require('query-string');

	queryString.stringify({a: 1, b: undefined, c: null, d: 4}, {
		skipNull: true
	});
	//=> 'a=1&d=4'

	queryString.stringify({a: undefined, b: null}, {
		skipNull: true
	});
	//=> ''
	```
	*/
	readonly skipNull?: boolean;

	/**
	Skip keys with an empty string as the value.

	@default false

	@example
	```
	import queryString = require('query-string');

	queryString.stringify({a: 1, b: '', c: '', d: 4}, {
		skipEmptyString: true
	});
	//=> 'a=1&d=4'
	```

	@example
	```
	import queryString = require('query-string');

	queryString.stringify({a: '', b: ''}, {
		skipEmptyString: true
	});
	//=> ''
	```
	*/
	readonly skipEmptyString?: boolean;
}

export type Stringifiable = string | boolean | number | null | undefined;

export type StringifiableRecord = Record<
	string,
	Stringifiable | Stringifiable[]
>;

/**
Stringify an object into a query string and sort the keys.
*/
export function stringify(
	object: StringifiableRecord,
	options?: StringifyOptions
): string;

/**
Extract a query string from a URL that can be passed into `.parse()`.

Note: This behaviour can be changed with the `skipNull` option.
*/
export function extract(url: string): string;

export interface UrlObject {
	readonly url: string;

	/**
	Overrides queries in the `url` property.
	*/
	readonly query: StringifiableRecord;

	/**
	Overrides the fragment identifier in the `url` property.
	*/
	readonly fragmentIdentifier?: string;
}

/**
Stringify an object into a URL with a query string and sorting the keys. The inverse of [`.parseUrl()`](https://github.com/sindresorhus/query-string#parseurlstring-options)

Query items in the `query` property overrides queries in the `url` property.

The `fragmentIdentifier` property overrides the fragment identifier in the `url` property.

@example
```
queryString.stringifyUrl({url: 'https://foo.bar', query: {foo: 'bar'}});
//=> 'https://foo.bar?foo=bar'

queryString.stringifyUrl({url: 'https://foo.bar?foo=baz', query: {foo: 'bar'}});
//=> 'https://foo.bar?foo=bar'

queryString.stringifyUrl({
	url: 'https://foo.bar',
	query: {
		top: 'foo'
	},
	fragmentIdentifier: 'bar'
});
//=> 'https://foo.bar?top=foo#bar'
```
*/
export function stringifyUrl(
	object: UrlObject,
	options?: StringifyOptions
): string;
