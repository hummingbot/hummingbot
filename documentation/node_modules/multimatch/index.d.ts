import {IOptions} from 'minimatch';

declare namespace multimatch {
	type Options = Readonly<IOptions>;
}

/**
Extends [`minimatch.match()`](https://github.com/isaacs/minimatch#minimatchmatchlist-pattern-options) with support for multiple patterns.

@param paths - Paths to match against.
@param patterns - Globbing patterns to use. For example: `['*', '!cake']`. See supported [`minimatch` patterns](https://github.com/isaacs/minimatch#usage).
@returns The matching paths.

@example
```
import multimatch = require('multimatch');

multimatch(['unicorn', 'cake', 'rainbows'], ['*', '!cake']);
//=> ['unicorn', 'rainbows']
```
*/
declare function multimatch(
	paths: string | string[],
	patterns: string | string[],
	options?: multimatch.Options
): string[];

export = multimatch;
