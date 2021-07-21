import * as deriving from './helpers/Wonka_deriving';
import * as sources from './Wonka_sources.gen';
import * as operators from './Wonka_operators.gen';
import * as types from './Wonka_types.gen';
import * as web from './web/WonkaJs.gen';

import callbagFromArray from 'callbag-from-iter';
import Observable from 'zen-observable';

const collectSignals = (
  source: types.sourceT<any>,
  onStart?: (talkbackCb: (tb: types.talkbackT) => void) => void
) => {
  let talkback = null;
  const signals = [];

  source(signal => {
    signals.push(signal);
    if (deriving.isStart(signal)) {
      talkback = deriving.unboxStart(signal);
      if (onStart) onStart(talkback);
      talkback(deriving.pull);
    } else if (deriving.isPush(signal)) {
      talkback(deriving.pull);
    }
  })

  return signals;
};

/* When a Close talkback signal is sent the source should immediately end */
const passesActiveClose = (source: types.sourceT<any>) =>
  it('stops emitting when a Close talkback signal is received (spec)', () => {
    let talkback = null;

    const sink: types.sinkT<any> = signal => {
      expect(deriving.isPush(signal)).toBeFalsy();
      expect(deriving.isEnd(signal)).toBeFalsy();
      if (deriving.isStart(signal)) {
        talkback = deriving.unboxStart(signal);
        talkback(deriving.close);
      }
    };

    source(sink);
    expect(talkback).not.toBe(null);
  });

/* All synchronous, cold sources won't send anything unless a Pull signal
  has been received. */
const passesColdPull = (source: types.sourceT<any>) =>
  it('sends nothing when no Pull talkback signal has been sent (spec)', () => {
    let pushes = 0;
    let talkback = null;

    const sink: types.sinkT<any> = signal => {
      if (deriving.isPush(signal)) {
        pushes++;
      } else if (deriving.isStart(signal)) {
        talkback = deriving.unboxStart(signal);
      }
    };

    source(sink);
    expect(talkback).not.toBe(null);
    expect(pushes).toBe(0);

    setTimeout(() => {
      expect(pushes).toBe(0);
      talkback(deriving.pull);
    }, 10);

    jest.runAllTimers();
    expect(pushes).toBe(1);
  });

/* All synchronous, cold sources need to use trampoline scheduling to avoid
  recursively sending more and more Push signals which would eventually lead
  to a call stack overflow when too many values are emitted. */
const passesTrampoline = (source: types.sourceT<any>) =>
  it('uses trampoline scheduling instead of recursive push signals (spec)', () => {
    let talkback = null;
    let pushes = 0;

    const signals = [];
    const sink: types.sinkT<any> = signal => {
      if (deriving.isPush(signal)) {
        const lastPushes = ++pushes;
        signals.push(signal);
        talkback(deriving.pull);
        expect(lastPushes).toBe(pushes);
      } else if (deriving.isStart(signal)) {
        talkback = deriving.unboxStart(signal);
        talkback(deriving.pull);
        expect(pushes).toBe(2);
      } else if (deriving.isEnd(signal)) {
        signals.push(signal);
        expect(pushes).toBe(2);
      }
    };

    source(sink);

    expect(signals).toEqual([
      deriving.push(1),
      deriving.push(2),
      deriving.end(),
    ]);
  });

beforeEach(() => {
  jest.useFakeTimers();
});

describe('fromArray', () => {
  passesTrampoline(sources.fromArray([1, 2]));
  passesColdPull(sources.fromArray([0]));
  passesActiveClose(sources.fromArray([0]));
});

describe('fromList', () => {
  passesTrampoline(sources.fromList([1, [2]] as any));
  passesColdPull(sources.fromList([0] as any));
  passesActiveClose(sources.fromList([0] as any));
});

describe('fromValue', () => {
  passesColdPull(sources.fromValue(0));
  passesActiveClose(sources.fromValue(0));

  it('sends a single value and ends', () => {
    expect(collectSignals(sources.fromValue(1))).toEqual([
      deriving.start(expect.any(Function)),
      deriving.push(1),
      deriving.end()
    ]);
  });
});

describe('merge', () => {
  const source = operators.merge<any>([
    sources.fromValue(0),
    sources.empty
  ]);

  passesColdPull(source);
  passesActiveClose(source);

  it('correctly merges two sources where the second is empty', () => {
    const source = operators.merge<any>([
      sources.fromValue(0),
      sources.empty
    ]);

    expect(collectSignals(source)).toEqual([
      deriving.start(expect.any(Function)),
      deriving.push(0),
      deriving.end(),
    ]);
  });

  it('correctly merges hot sources', () => {
    const onStart = jest.fn();
    const source = operators.merge<any>([
      operators.onStart(onStart)(sources.never),
      operators.onStart(onStart)(sources.fromArray([1, 2])),
    ]);

    const signals = collectSignals(source);
    expect(onStart).toHaveBeenCalledTimes(2);

    expect(signals).toEqual([
      deriving.start(expect.any(Function)),
      deriving.push(1),
      deriving.push(2),
    ]);
  });

  it('correctly merges asynchronous sources', () => {
    jest.useFakeTimers();

    const onStart = jest.fn();
    const source = operators.merge<any>([
      operators.onStart(onStart)(sources.fromValue(-1)),
      operators.onStart(onStart)(
        operators.take(2)(web.interval(50))
      ),
    ]);

    const signals = collectSignals(source);
    jest.advanceTimersByTime(100);
    expect(onStart).toHaveBeenCalledTimes(2);

    expect(signals).toEqual([
      deriving.start(expect.any(Function)),
      deriving.push(-1),
      deriving.push(0),
      deriving.push(1),
      deriving.end(),
    ]);
  });
});

describe('concat', () => {
  const source = operators.concat<any>([
    sources.fromValue(0),
    sources.empty
  ]);

  passesColdPull(source);
  passesActiveClose(source);

  it('correctly concats two sources where the second is empty', () => {
    const source = operators.concat<any>([
      sources.fromValue(0),
      sources.empty
    ]);

    expect(collectSignals(source)).toEqual([
      deriving.start(expect.any(Function)),
      deriving.push(0),
      deriving.end(),
    ]);
  });
});

describe('make', () => {
  it('may be used to create async sources', () => {
    const teardown = jest.fn();
    const source = sources.make(observer => {
      setTimeout(() => observer.next(1), 10);
      setTimeout(() => observer.complete(), 20);
      return teardown;
    });

    const signals = collectSignals(source);
    expect(signals).toEqual([deriving.start(expect.any(Function))]);
    jest.runAllTimers();

    expect(signals).toEqual([
      deriving.start(expect.any(Function)),
      deriving.push(1),
      deriving.end(),
    ]);
  });

  it('supports active cancellation', () => {
    const teardown = jest.fn();
    const source = sources.make(() => teardown);

    const sink: types.sinkT<any> = signal => {
      expect(deriving.isPush(signal)).toBeFalsy();
      expect(deriving.isEnd(signal)).toBeFalsy();
      if (deriving.isStart(signal))
        setTimeout(() => deriving.unboxStart(signal)(deriving.close));
    };

    source(sink);
    expect(teardown).not.toHaveBeenCalled();
    jest.runAllTimers();
    expect(teardown).toHaveBeenCalled();
  });
});

describe('makeSubject', () => {
  it('may be used to emit signals programmatically', () => {
    const { source, next, complete } = sources.makeSubject();
    const signals = collectSignals(source);

    expect(signals).toEqual([
      deriving.start(expect.any(Function)),
    ]);

    next(1);

    expect(signals).toEqual([
      deriving.start(expect.any(Function)),
      deriving.push(1),
    ]);

    complete();

    expect(signals).toEqual([
      deriving.start(expect.any(Function)),
      deriving.push(1),
      deriving.end(),
    ]);
  });

  it('ignores signals after complete has been called', () => {
    const { source, next, complete } = sources.makeSubject();
    const signals = collectSignals(source);
    complete();

    expect(signals).toEqual([
      deriving.start(expect.any(Function)),
      deriving.end(),
    ]);

    next(1);
    complete();
    expect(signals.length).toBe(2);
  });
});

describe('never', () => {
  it('emits nothing and ends immediately', () => {
    const signals = collectSignals(sources.never);
    expect(signals).toEqual([deriving.start(expect.any(Function)) ]);
  });
});

describe('empty', () => {
  it('emits nothing and ends immediately', () => {
    const signals = collectSignals(sources.empty);

    expect(signals).toEqual([
      deriving.start(expect.any(Function)),
      deriving.end(),
    ]);
  });
});

describe('fromPromise', () => {
  passesActiveClose(web.fromPromise(Promise.resolve(null)));

  it('emits a value when the promise resolves', async () => {
    const promise = Promise.resolve(1);
    const signals = collectSignals(web.fromPromise(promise));

    expect(signals).toEqual([
      deriving.start(expect.any(Function)),
    ]);

    await promise;

    expect(signals).toEqual([
      deriving.start(expect.any(Function)),
      deriving.push(1),
      deriving.end(),
    ]);
  });
});

describe('fromObservable', () => {
  beforeEach(() => {
    jest.useRealTimers();
  });

  it('converts an Observable to a Wonka source', async () => {
    const source = web.fromObservable(Observable.from([1, 2]));
    const signals = collectSignals(source);

    await new Promise(resolve => setTimeout(resolve));

    expect(signals).toEqual([
      deriving.start(expect.any(Function)),
      deriving.push(1),
      deriving.push(2),
      deriving.end(),
    ]);
  });

  it('supports cancellation on converted Observables', async () => {
    const source = web.fromObservable(Observable.from([1, 2]));
    const signals = collectSignals(source, talkback => {
      talkback(deriving.close);
    });

    await new Promise(resolve => setTimeout(resolve));

    expect(signals).toEqual([
      deriving.start(expect.any(Function)),
    ]);
  });
});

describe('fromCallbag', () => {
  it('converts a Callbag to a Wonka source', () => {
    const source = web.fromCallbag(callbagFromArray([1, 2]));
    const signals = collectSignals(source);

    expect(signals).toEqual([
      deriving.start(expect.any(Function)),
      deriving.push(1),
      deriving.push(2),
      deriving.end(),
    ]);
  });

  it('supports cancellation on converted Observables', () => {
    const source = web.fromCallbag(callbagFromArray([1, 2]));
    const signals = collectSignals(source, talkback => {
      talkback(deriving.close);
    });

    expect(signals).toEqual([
      deriving.start(expect.any(Function)),
    ]);
  });
});

describe('interval', () => {
  it('emits Push signals until Cancel is sent', () => {
    let pushes = 0;
    let talkback = null;

    const sink: types.sinkT<any> = signal => {
      if (deriving.isPush(signal)) {
        pushes++;
      } else if (deriving.isStart(signal)) {
        talkback = deriving.unboxStart(signal);
      }
    };

    web.interval(100)(sink);
    expect(talkback).not.toBe(null);
    expect(pushes).toBe(0);

    jest.advanceTimersByTime(100);
    expect(pushes).toBe(1);
    jest.advanceTimersByTime(100);
    expect(pushes).toBe(2);

    talkback(deriving.close);
    jest.advanceTimersByTime(100);
    expect(pushes).toBe(2);
  });
});

describe('fromDomEvent', () => {
  it('emits Push signals for events on a DOM element', () => {
    let talkback = null;

    const element = {
      addEventListener: jest.fn(),
      removeEventListener: jest.fn(),
    };

    const sink: types.sinkT<any> = signal => {
      expect(deriving.isEnd(signal)).toBeFalsy();
      if (deriving.isStart(signal))
        talkback = deriving.unboxStart(signal);
    };

    web.fromDomEvent(element as any, 'click')(sink);

    expect(element.addEventListener).toHaveBeenCalledWith('click', expect.any(Function));
    expect(element.removeEventListener).not.toHaveBeenCalled();
    const listener = element.addEventListener.mock.calls[0][1];

    listener(1);
    listener(2);
    talkback(deriving.close);
    expect(element.removeEventListener).toHaveBeenCalledWith('click', listener);
  });
});
