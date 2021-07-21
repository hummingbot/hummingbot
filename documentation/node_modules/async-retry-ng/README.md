# async-retry-ng

[![Code Style](https://badgen.net/badge/code%20style/airbnb/fd5c63)](https://github.com/airbnb/javascript)

Retrying made simple, easy, and async.

## Usage

```js
// Packages
const retry = require('async-retry-ng')
const fetch = require('node-fetch')

await retry(async bail => {
  // if anything throws, we retry
  const res = await fetch('https://google.com')

  if (403 === res.status) {
    // don't retry upon 403
    bail(new Error('Unauthorized'))
    return
  }

  const data = await res.text()
  return data.substr(0, 500)
}, {
  retries: 5
})
```

### API

```js
retry(retrier : Function, opts : Object) => Promise
```

- The supplied function can be `async` or not. In other words, it can be a function that returns a `Promise` or a value.
- The supplied function receives two parameters
  1. A `Function` you can invoke to abort the retrying (bail)
  2. A `Number` identifying the attempt. The absolute first attempt (before any retries) is `1`.
- The `opts`
  * `retries`: The maximum amount of times to retry the operation. Default is `10`.
  * `factor`: The exponential factor to use. Default is `2`.
  * `minTimeout`: The number of milliseconds before starting the first retry. Default is `1000`.
  * `maxTimeout`: The maximum number of milliseconds between two retries. Default is `Infinity`.
  * `randomize`: Randomizes the timeouts by multiplying with a factor between `1` to `2`. Default is `true`.
  * `onRetry`: an optional `Function` that is invoked after a new retry is performed. It's passed the `Error` that triggered it as a parameter.

All time values are in milliseconds.

### Retries Explained

The formula used to calculate the individual timeouts is:

```
Math.min(random * minTimeout * Math.pow(factor, attempt), maxTimeout)
```

Have a look at [this article][article] for a better explanation of approach.

If you want to tune your `factor` / `times` settings to attempt the last retry
after a certain amount of time, you can use wolfram alpha. For example in order
to tune for `10` attempts in `5 minutes`, you can use this equation:

![screenshot](https://github.com/OlliV/async-retry-ng/raw/master/equation.gif)

Explaining the various values from left to right:

* `k = 0 ... 9`:  The `retries` value (10)
* `1000`: The `minTimeout` value in ms (1000)
* `x^k`: No need to change this, `x` will be your resulting factor
* `5 * 60 * 1000`: The desired total amount of time for retrying in ms (5 minutes)

To make this a little easier for you, use wolfram alpha to do the calculations:

<http://www.wolframalpha.com/input/?i=Sum%5B1000*x^k%2C+{k%2C+0%2C+9}%5D+%3D+5+*+60+*+1000>

[article]: http://dthain.blogspot.com/2009/02/exponential-backoff-in-distributed.html
