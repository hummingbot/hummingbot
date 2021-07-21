# ts-easing

Collection of easing function in TypeScript.

All functions accept a number in range of `[0..1]`.

All functions return a number, which is guaranteed to start at 0 and end at 1.

```
f(t), where t in [0..1]

f(0) -> 0
f(1) -> 1
```


## Usage

```js
import {easing} from 'ts-easing';

console.log(easing.quadratic(0.5));
```


## License

[Unlicense](./LICENSE) &mdash; public domain.
