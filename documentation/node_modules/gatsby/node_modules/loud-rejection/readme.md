# loud-rejection [![Build Status](https://travis-ci.org/sindresorhus/loud-rejection.svg?branch=master)](https://travis-ci.org/sindresorhus/loud-rejection) [![Coverage Status](https://coveralls.io/repos/github/sindresorhus/loud-rejection/badge.svg?branch=master)](https://coveralls.io/github/sindresorhus/loud-rejection?branch=master)

> Make unhandled promise rejections fail loudly instead of the default [silent fail](https://gist.github.com/benjamingr/0237932cee84712951a2)

By default, promises fail silently if you don't attach a `.catch()` handler to them.

This tool keeps track of unhandled rejections globally. If any remain unhandled at the end of your process, it logs them to STDERR and exits with code 1.

Use this in top-level things like tests, CLI tools, apps, etc, **but not in reusable modules.**<br>
Not needed in the browser as unhandled rejections are shown in the console.


## Install

```
$ npm install loud-rejection
```


## Usage

```js
const loudRejection = require('loud-rejection');
const promiseFunction = require('promise-fn');

// Install the `unhandledRejection` listeners
loudRejection();

promiseFunction();
```

Without this module it's more verbose and you might even miss some that will fail silently:

```js
const promiseFunction = require('promise-fn');

function error(error) {
	console.error(error.stack);
	process.exit(1);
}

promiseFunction().catch(error);
```

### Register script

Alternatively to the above, you may simply require `loud-rejection/register` and the unhandledRejection listener will be automagically installed for you.

This is handy for ES2015 imports:

```js
import 'loud-rejection/register';
```


## API

### loudRejection([log])

#### log

Type: `Function`<br>
Default: `console.error`

Custom logging function to print the rejected promise. Receives the error stack.


## Related

- [hard-rejection](https://github.com/sindresorhus/hard-rejection) - Make unhandled promise rejections fail hard right away instead of the default silent fail
- [More…](https://github.com/sindresorhus/promise-fun)


---

<div align="center">
	<b>
		<a href="https://tidelift.com/subscription/pkg/npm-loud-rejection?utm_source=npm-loud-rejection&utm_medium=referral&utm_campaign=readme">Get professional support for this package with a Tidelift subscription</a>
	</b>
	<br>
	<sub>
		Tidelift helps make open source sustainable for maintainers while giving companies<br>assurances about security, maintenance, and licensing for their dependencies.
	</sub>
</div>
