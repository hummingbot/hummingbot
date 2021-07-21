# Colorette [![](https://img.shields.io/npm/v/colorette.svg?label=&color=2a64e6)](https://www.npmjs.org/package/colorette)

> Color your terminal using pure idiomatic JavaScript.

Colorette is a Node.js library for embellishing your CLI tools with colors and styles using [ANSI escape codes](https://en.wikipedia.org/wiki/ANSI_escape_code).

- ~1.5x faster than alternatives ([run the benchmarks](#run-the-benchmarks)).
- No wonky prototype-based method chains.
- Automatic color support detection.
- ~80 LOC and no dependencies.
- [`NO_COLOR`](https://no-color.org) friendly.

## Quickstart

```console
npm i colorette
```

Import the [styles](#styles) you need. [Here](#supported-styles)'s the list of styles you can use.

```js
import { red, blue, bold } from "colorette"
```

Wrap your strings in one or more styles to produce the finish you're looking for.

```js
console.log(bold(blue("Engage!")))
```

Mix it with [template literals](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Template_literals) to interpolate variables, expressions and create multi-line strings easily.

```js
console.log(`
  Beets are ${red("red")},
  Plums are ${blue("blue")},
  ${bold("Colorette!")}.
`)
```

Using `console.log`'s [string substitution](https://nodejs.org/api/console.html#console_console_log_data_args) can be useful too.

```js
console.log(bold("Total: $%f"), 1.99)
```

You can also nest styles without breaking existing escape codes.

```js
console.log(red(`Red Shirt ${blue("Blue Shirt")} Red Shirt`))
```

Feeling adventurous? Try the [pipeline operator](https://github.com/tc39/proposal-pipeline-operator).

```js
console.log("Make it so!" |> bold |> blue)
```

## Supported styles

Colorette supports the standard and bright color variations out-of-the-box. See [this issue](https://github.com/jorgebucaran/colorette/issues/27) if you were looking for TrueColor support.

| Colors  | Background Colors | Bright Colors | Bright Background Colors | Modifiers         |
| ------- | ----------------- | ------------- | ------------------------ | ----------------- |
| black   | bgBlack           | blackBright   | bgBlackBright            | dim               |
| red     | bgRed             | redBright     | bgRedBright              | **bold**          |
| green   | bgGreen           | greenBright   | bgGreenBright            | hidden            |
| yellow  | bgYellow          | yellowBright  | bgYellowBright           | _italic_          |
| blue    | bgBlue            | blueBright    | bgBlueBright             | underline         |
| magenta | bgMagenta         | magentaBright | bgMagentaBright          | ~~strikethrough~~ |
| cyan    | bgCyan            | cyanBright    | bgCyanBright             | reset             |
| white   | bgWhite           | whiteBright   | bgWhiteBright            |                   |
| gray    |                   |               |                          |                   |

## API

### <code><i>style</i>(string)</code>

Returns a string wrapped in the corresponding ANSI escape codes.

```js
red("Red Alert") //=> \u001b[31mRed Alert\u001b[39m
```

### `options.enabled`

Color will be enabled if your terminal supports it, `FORCE_COLOR` is defined in [`process.env`](https://nodejs.org/dist/latest-v8.x/docs/api/process.html#process_process_env) and if `NO_COLOR` isn't, but you can always override it if you want.

```js
import { options } from "colorette"

options.enabled = false
```

## Run the benchmarks

```
npm i -C bench && node bench
```

<pre>
colorette × 759,429 ops/sec
chalk × 524,034 ops/sec
kleur × 490,347 ops/sec
colors × 255,661 ops/sec
ansi-colors × 317,605 ops/sec
</pre>

## License

[MIT](LICENSE.md)
