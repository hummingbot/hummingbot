/// <reference types="node"/>
import {EventEmitter} from 'events';

declare namespace PQueue {
	interface QueueAddOptions {
		[key: string]: unknown;
	}

	interface QueueClass<EnqueueOptionsType extends QueueAddOptions> {
		size: number;

		enqueue(run: () => void, options?: EnqueueOptionsType): void;

		dequeue(): (() => void) | undefined;
	}

	interface QueueClassConstructor<EnqueueOptionsType extends QueueAddOptions> {
		new (): QueueClass<EnqueueOptionsType>;
	}

	interface Options<EnqueueOptionsType extends QueueAddOptions> {
		/**
		Concurrency limit. Minimum: `1`.

		@default Infinity
		*/
		concurrency?: number;

		/**
		Whether queue tasks within concurrency limit, are auto-executed as soon as they're added.

		@default true
		*/
		autoStart?: boolean;

		/**
		Class with a `enqueue` and `dequeue` method, and a `size` getter. See the [Custom QueueClass](https://github.com/sindresorhus/p-queue#custom-queueclass) section.
		*/
		queueClass?: QueueClassConstructor<EnqueueOptionsType>;

		/**
		The max number of runs in the given interval of time. Minimum: `1`.

		@default Infinity
		*/
		intervalCap?: number;

		/**
		The length of time in milliseconds before the interval count resets. Must be finite. Minimum: `0`.

		@default 0
		*/
		interval?: number;

		/**
		Whether the task must finish in the given interval or will be carried over into the next interval count.

		@default false
		*/
		carryoverConcurrencyCount?: boolean;
	}

	interface DefaultAddOptions {
		/**
		Priority of operation. Operations with greater priority will be scheduled first.

		@default 0
		*/
		priority?: number;
	}

	type Task<TaskResultType> =
		| (() => PromiseLike<TaskResultType>)
		| (() => TaskResultType);
}

/**
Promise queue with concurrency control.
*/
declare class PQueue<
	EnqueueOptionsType extends PQueue.QueueAddOptions = PQueue.DefaultAddOptions
> extends EventEmitter {
	/**
	Size of the queue.
	*/
	readonly size: number;

	/**
	Number of pending promises.
	*/
	readonly pending: number;

	/**
	Whether the queue is currently paused.
	*/
	readonly isPaused: boolean;

	constructor(options?: PQueue.Options<EnqueueOptionsType>);

	/**
	Adds a sync or async task to the queue. Always returns a promise.

	@param fn - Promise-returning/async function.
	*/
	add<TaskResultType>(
		fn: PQueue.Task<TaskResultType>,
		options?: EnqueueOptionsType
	): Promise<TaskResultType>;

	/**
	Same as `.add()`, but accepts an array of sync or async functions.

	@param fn - Array of Promise-returning/async functions.
	@returns A promise that resolves when all functions are resolved.
	*/
	addAll<TaskResultsType>(
		fns: PQueue.Task<TaskResultsType>[],
		options?: EnqueueOptionsType
	): Promise<TaskResultsType[]>;

	/**
	Can be called multiple times. Useful if you for example add additional items at a later time.

	@returns A promise that settles when the queue becomes empty.
	*/
	onEmpty(): Promise<void>;

	/**
	The difference with `.onEmpty` is that `.onIdle` guarantees that all work from the queue has finished. `.onEmpty` merely signals that the queue is empty, but it could mean that some promises haven't completed yet.

	@returns A promise that settles when the queue becomes empty, and all promises have completed; `queue.size === 0 && queue.pending === 0`.
	*/
	onIdle(): Promise<void>;

	/**
	Start (or resume) executing enqueued tasks within concurrency limit. No need to call this if queue is not paused (via `options.autoStart = false` or by `.pause()` method.)
	*/
	start(): void;

	/**
	Clear the queue.
	*/
	clear(): void;

	/**
	Put queue execution on hold.
	*/
	pause(): void;

	addListener(event: 'active', listener: () => void): this;
	on(event: 'active', listener: () => void): this;
	once(event: 'active', listener: () => void): this;
	prependListener(event: 'active', listener: () => void): this;
	prependOnceListener(event: 'active', listener: () => void): this;
	removeListener(event: 'active', listener: () => void): this;
	off(event: 'active', listener: () => void): this;
	removeAllListeners(event?: 'active'): this;
	listeners(event: 'active'): (() => void)[];
	rawListeners(event: 'active'): (() => void)[];
	emit(event: 'active'): boolean;
	eventNames(): 'active'[];
	listenerCount(type: 'active'): number;
}

export = PQueue;
