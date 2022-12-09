import { v4 as uuidv4 } from 'uuid';

/**
 * A referencing counting implementation for getInstance(), which guarantees
 * shared instances would not be closed prematurely. Think about the following
 * case:
 *
 * 1. You have an Ethereum instance, an Avalanche instance, and a Harmony
 *    instance - all of them depend on a shared database object.
 * 2. Let's say you call `avalanche.close()`. The shared database object should
 *    NOT be closed at this point - since the Ethereum and Harmony instances
 *    may still want to use it.
 * 3. But let's say `harmony.close()` and `ethereum.close()` are also called,
 *    the shared database should be closed at the last close call - because
 *    once that's called, there's no longer anyone owning the shared database
 *    object.
 *
 * This class provides smarter `getInstance()` and `close()` functions that are
 * aware of ownership relation between objects, and use reference counting to
 * determine whether an underlying object should actually be finalized or not
 * when close() is called.
 *
 * In the above example, when `avalanche.close()` is called, the class would
 * understand that the shared database object is still owned by the `ethereum`
 * and `harmony` objects. So the shared database object wouldn't be finalized.
 *
 * When `ethereum.close()` is called, the class would see that there's no more
 * object referencing the shared database, and thus it would finalize the
 * database object.
 *
 * Every `ReferenceCountingCloseable` object has a retrieval key and a handle.
 *
 * The retrieval key is the shared object ID for use with `getInstance()`.
 * Typically, this has to do with the shared object's semantics, like Ethereum
 * network name, or database file path.
 *
 * The handle is the closeable object's random unique ID, used for declaring
 * ownership of another shared object. When `getInstance(key, handle)` is called
 * with object A's handle to retrieve object B, it means object A owns object B.
 * Shared object B's `close()` function would only finalize it when all owning
 * objects have also finalized.
 */
export class ReferenceCountingCloseable {
  private static _retrievalMap: {
    [key: string]: ReferenceCountingCloseable;
  } = {};
  private static _refCounts: { [key: string]: Set<string> } = {};
  private readonly _retrievalKey: string;
  private readonly _handle: string;

  /**
   * Constructs a new closeable object with reference counting.
   *
   * @param retrievalKey Key for use with getInstance()
   * @protected
   */
  protected constructor(retrievalKey: string) {
    this._retrievalKey = retrievalKey;
    this._handle = ReferenceCountingCloseable.createHandle();
  }

  /**
   * Shared object retrieval key for use with `getInstance()`.
   */
  get retrievalKey(): string {
    return this._retrievalKey;
  }

  /**
   * Object ID for declaring ownership relation on `getInstance()`.
   */
  get handle(): string {
    return this._handle;
  }

  /**
   * How many ownership relations are pointing towards this object?
   */
  get refCount(): number {
    const fullKey: string = `${this.constructor.name}/${this.retrievalKey}`;
    if (fullKey in ReferenceCountingCloseable._refCounts) {
      return ReferenceCountingCloseable._refCounts[fullKey].size;
    }
    return 0;
  }

  /**
   * Creates a randomized object handle string.
   */
  public static createHandle(): string {
    return uuidv4();
  }

  /**
   * Retrieves a shared object of the current class, given a retrieval key and
   * the owner's handle.
   *
   * @param retrievalKey Retrieval key for shared object
   * @param ownerHandle Handle string of owner object
   */
  public static getInstance<T extends ReferenceCountingCloseable>(
    retrievalKey: string,
    ownerHandle: string
  ): T {
    const fullKey: string = `${this.name}/${retrievalKey}`;
    if (fullKey in ReferenceCountingCloseable._retrievalMap) {
      ReferenceCountingCloseable._refCounts[fullKey].add(ownerHandle);
      return ReferenceCountingCloseable._retrievalMap[fullKey] as T;
    }

    const instance: ReferenceCountingCloseable =
      this.createInstanceFromKey(retrievalKey);
    ReferenceCountingCloseable._retrievalMap[fullKey] = instance;
    ReferenceCountingCloseable._refCounts[fullKey] = new Set([ownerHandle]);

    return instance as T;
  }

  /**
   * Creates an instance of the current class, given a retrieval key. A default
   * implementation is provided, but this can be overridden if a child class
   * requires a different implementation. This function is called by
   * `getInstance()` if there's no existing shared object for a retrieval key.
   *
   * @param retrievalKey Retrieval key for shared object
   */
  public static createInstanceFromKey(
    retrievalKey: string
  ): ReferenceCountingCloseable {
    return new this(retrievalKey);
  }

  /**
   * Declares ownership of this object to a handle string. This is useful when
   * you wish to declare a closeable object to be owned by an outside object.
   *
   * @param ownerHandle Handle string representing the owner object.
   */
  public declareOwnership(ownerHandle: string) {
    const fullKey: string = `${this.constructor.name}/${this.retrievalKey}`;
    if (!(fullKey in ReferenceCountingCloseable._retrievalMap)) {
      ReferenceCountingCloseable._retrievalMap[fullKey] = this;
    }
    if (!(fullKey in ReferenceCountingCloseable._refCounts)) {
      ReferenceCountingCloseable._refCounts[fullKey] = new Set([ownerHandle]);
    } else {
      ReferenceCountingCloseable._refCounts[fullKey].add(ownerHandle);
    }
  }

  /**
   * Close with reference counting. This declares the owner object represented
   * by `ownerHandle` is disposing of this object. If this object has no more
   * owners, it should finalize itself (e.g. closing the underlying database,
   * network connection, etc.)
   *
   * This is expected to be overridden by child classes. Typically, every child
   * class should override this function to do two things:
   *
   * 1. Call `await super.close(ownerHandle);`.
   * 2. If its own reference count is now 0, finalize itself:
   *   i.  Call `await close()` for all other `ReferenceCountingCloseable`
   *       objects it owns.
   *   ii. Finalize / release any system resource it owns, e.g. database
   *       handles or network connections.
   *
   * @param ownerHandle
   */
  public async close(ownerHandle: string): Promise<void> {
    const fullKey: string = `${this.constructor.name}/${this.retrievalKey}`;
    if (fullKey in ReferenceCountingCloseable._retrievalMap) {
      ReferenceCountingCloseable._refCounts[fullKey].delete(ownerHandle);
      if (ReferenceCountingCloseable._refCounts[fullKey].size < 1) {
        delete ReferenceCountingCloseable._refCounts[fullKey];
        delete ReferenceCountingCloseable._retrievalMap[fullKey];
      }
    }
  }
}
