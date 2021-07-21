declare const loudRejection: {
	/**
	Make unhandled promise rejections fail loudly instead of the default [silent fail](https://gist.github.com/benjamingr/0237932cee84712951a2).

	@param log - Custom logging function to print the rejected promise. Receives the error stack. Default: `console.error`.

	@example
	```
	import loudRejection = require('loud-rejection');
	import promiseFunction = require('promise-fn');

	// Install the `unhandledRejection` listeners
	loudRejection();

	promiseFunction();
	```
	*/
	(log?: (stack: string) => void): void;

	// TODO: remove this in the next major version, refactor the whole definition to:
	// declare function loudRejection(log?: (stack: string) => void): void;
	// export = loudRejection;
	default: typeof loudRejection;
};

export = loudRejection;
