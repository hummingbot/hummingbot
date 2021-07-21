# d3-random

Generate random numbers from various distributions.

## Installing

If you use NPM, `npm install d3-random`. Otherwise, download the [latest release](https://github.com/d3/d3-random/releases/latest). You can also load directly from [d3js.org](https://d3js.org), either as a [standalone library](https://d3js.org/d3-random.v1.min.js) or as part of [D3 4.0](https://github.com/d3/d3). AMD, CommonJS, and vanilla environments are supported. In vanilla, a `d3` global is exported:

```html
<script src="https://d3js.org/d3-random.v1.min.js"></script>
<script>

var random = d3.randomUniform(1, 10);

</script>
```

[Try d3-random in your browser.](https://runkit.com/npm/d3-random)

## API Reference

<a name="randomUniform" href="#randomUniform">#</a> d3.<b>randomUniform</b>([<i>min</i>, ][<i>max</i>]) [<>](https://github.com/d3/d3-random/blob/master/src/uniform.js "Source")

Returns a function for generating random numbers with a [uniform distribution](https://en.wikipedia.org/wiki/Uniform_distribution_\(continuous\)). The minimum allowed value of a returned number is *min*, and the maximum is *max*. If *min* is not specified, it defaults to 0; if *max* is not specified, it defaults to 1. For example:

```js
d3.randomUniform(6)(); // Returns a number greater than or equal to 0 and less than 6.
d3.randomUniform(1, 5)(); // Returns a number greater than or equal to 1 and less than 5.
```

Note that you can also use the built-in [Math.random](https://developer.mozilla.org/en-US/docs/JavaScript/Reference/Global_Objects/Math/random) to generate uniform distributions directly. For example, to generate a random integer between 0 and 99 (inclusive), you can say `Math.random() * 100 | 0`.

<a name="randomNormal" href="#randomNormal">#</a> d3.<b>randomNormal</b>([<i>mu</i>][, <i>sigma</i>]) [<>](https://github.com/d3/d3-random/blob/master/src/normal.js "Source")

Returns a function for generating random numbers with a [normal (Gaussian) distribution](https://en.wikipedia.org/wiki/Normal_distribution). The expected value of the generated numbers is *mu*, with the given standard deviation *sigma*. If *mu* is not specified, it defaults to 0; if *sigma* is not specified, it defaults to 1.

<a name="randomLogNormal" href="#randomLogNormal">#</a> d3.<b>randomLogNormal</b>([<i>mu</i>][, <i>sigma</i>]) [<>](https://github.com/d3/d3-random/blob/master/src/logNormal.js "Source")

Returns a function for generating random numbers with a [log-normal distribution](https://en.wikipedia.org/wiki/Log-normal_distribution). The expected value of the random variable’s natural logarithm is *mu*, with the given standard deviation *sigma*. If *mu* is not specified, it defaults to 0; if *sigma* is not specified, it defaults to 1.

<a name="randomBates" href="#randomBates">#</a> d3.<b>randomBates</b>(<i>n</i>) [<>](https://github.com/d3/d3-random/blob/master/src/bates.js "Source")

Returns a function for generating random numbers with a [Bates distribution](https://en.wikipedia.org/wiki/Bates_distribution) with *n* independent variables.

<a name="randomIrwinHall" href="#randomIrwinHall">#</a> d3.<b>randomIrwinHall</b>(<i>n</i>) [<>](https://github.com/d3/d3-random/blob/master/src/irwinHall.js "Source")

Returns a function for generating random numbers with an [Irwin–Hall distribution](https://en.wikipedia.org/wiki/Irwin–Hall_distribution) with *n* independent variables.

<a name="randomExponential" href="#randomExponential">#</a> d3.<b>randomExponential</b>(<i>lambda</i>) [<>](https://github.com/d3/d3-random/blob/master/src/exponential.js "Source")

Returns a function for generating random numbers with an [exponential distribution](https://en.wikipedia.org/wiki/Exponential_distribution) with the rate *lambda*; equivalent to time between events in a [Poisson process](https://en.wikipedia.org/wiki/Poisson_point_process) with a mean of 1 / *lambda*. For example, exponential(1/40) generates random times between events where, on average, one event occurs every 40 units of time.

<a name="random_source" href="#random_source">#</a> <i>random</i>.<b>source</b>(<i>source</i>)

Returns the same type of function for generating random numbers but where the given random number generator *source* is used as the source of randomness instead of Math.random. The given random number generator must implement the same interface as Math.random and only return values in the range [0, 1). This is useful when a seeded random number generator is preferable to Math.random. For example:

```js
var d3 = require("d3-random"),
    seedrandom = require("seedrandom"),
    random = d3.randomNormal.source(seedrandom("a22ebc7c488a3a47"))(0, 1);

random(); // 0.9744193494813501
```
