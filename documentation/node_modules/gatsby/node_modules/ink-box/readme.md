# ink-box [![Build Status](https://travis-ci.org/sindresorhus/ink-box.svg?branch=master)](https://travis-ci.org/sindresorhus/ink-box)

> Styled box component for [Ink](https://github.com/vadimdemedes/ink)

![](screenshot.png)


## Install

```
$ npm install ink-box
```


## Usage

```js
import React from 'react';
import {render, Color} from 'ink';
import Box from 'ink-box';

render(
	<Box borderStyle="round" borderColor="cyan" float="center" padding={1}>
		I Love <Color magenta>Unicorns</Color>
	</Box>
);
```


## API

### `<Box>`

Props are passed as options to [`boxen`](https://github.com/sindresorhus/boxen#options).


## Related

- [ink-gradient](https://github.com/sindresorhus/ink-gradient) - Gradient color component for Ink
- [ink-link](https://github.com/sindresorhus/ink-link) - Link component for Ink
- [ink-big-text](https://github.com/sindresorhus/ink-big-text) - Awesome text component for Ink


## License

MIT © [Sindre Sorhus](https://sindresorhus.com)
