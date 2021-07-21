import * as deriving from './helpers/Wonka_deriving';
import * as sinks from './Wonka_sinks.gen';
import * as sources from './Wonka_sources.gen';
import * as web from './web/WonkaJs.gen';
import * as types from './Wonka_types.gen';

import Observable from 'zen-observable';
import callbagIterate from 'callbag-iterate';
import callbagTake from 'callbag-take';

describe('subscribe', () => {
  it('sends Pull talkback signals every Push signal', () => {
    let pulls = 0;
    const fn = jest.fn();

    const source: types.sourceT<any> = sink => {
      sink(deriving.start(tb => {
        if (tb === deriving.pull) {
          if (pulls < 3) {
            pulls++;
            sink(deriving.push(0));
          } else {
            sink(deriving.end());
            expect(pulls).toBe(3);
          }
        }
      }));
    };

    sinks.subscribe(fn)(source);
    expect(fn).toHaveBeenCalledTimes(3);
    expect(pulls).toBe(3);
  });

  it('cancels when unsubscribe is called', () => {
    let pulls = 0;
    let closing = 0;

    const source: types.sourceT<any> = sink => {
      sink(deriving.start(tb => {
        if (tb === deriving.pull) {
          if (!pulls) {
            pulls++;
            sink(deriving.push(0));
          }
        } else if (tb === deriving.close) {
          closing++;
        }
      }));
    };

    const sub = sinks.subscribe(() => {})(source);
    expect(pulls).toBe(1);

    sub.unsubscribe();
    expect(closing).toBe(1);
  });

  it('ignores cancellation when the source has already ended', () => {
    let pulls = 0;
    let closing = 0;

    const source: types.sourceT<any> = sink => {
      sink(deriving.start(tb => {
        if (tb === deriving.pull) {
          pulls++;
          sink(deriving.end());
        } else if (tb === deriving.close) {
          closing++;
        }
      }));
    };

    const sub = sinks.subscribe(() => {})(source);
    expect(pulls).toBe(1);
    sub.unsubscribe();
    expect(closing).toBe(0);
  });

  it('ignores Push signals after the source has ended', () => {
    const fn = jest.fn();
    const source: types.sourceT<any> = sink => {
      sink(deriving.start(tb => {
        if (tb === deriving.pull) {
          sink(deriving.end());
          sink(deriving.push(0));
        }
      }));
    };

    sinks.subscribe(fn)(source);
    expect(fn).not.toHaveBeenCalled();
  });

  it('ignores Push signals after cancellation', () => {
    const fn = jest.fn();
    const source: types.sourceT<any> = sink => {
      sink(deriving.start(tb => {
        if (tb === deriving.close) {
          sink(deriving.push(0));
        }
      }));
    };

    sinks.subscribe(fn)(source).unsubscribe();
    expect(fn).not.toHaveBeenCalled();
  });
});

describe('publish', () => {
  it('sends Pull talkback signals every Push signal', () => {
    let pulls = 0;
    const source: types.sourceT<any> = sink => {
      sink(deriving.start(tb => {
        if (tb === deriving.pull) {
          if (pulls < 3) {
            pulls++;
            sink(deriving.push(0));
          } else {
            sink(deriving.end());
            expect(pulls).toBe(3);
          }
        }
      }));
    };

    sinks.publish(source);
    expect(pulls).toBe(3);
  });
});

describe('toArray', () => {
  it('sends Pull talkback signals every Push signal', () => {
    let pulls = 0;
    const source: types.sourceT<any> = sink => {
      sink(deriving.start(tb => {
        if (tb === deriving.pull) {
          if (pulls < 3) {
            pulls++;
            sink(deriving.push(0));
          } else {
            sink(deriving.end());
            expect(pulls).toBe(3);
          }
        }
      }));
    };

    const array = sinks.toArray(source);
    expect(array).toEqual([0, 0, 0]);
    expect(pulls).toBe(3);
  });

  it('sends a Close talkback signal after all synchronous values have been pulled', () => {
    let pulls = 0;
    let ending = 0;

    const source: types.sourceT<any> = sink => {
      sink(deriving.start(tb => {
        if (tb === deriving.pull) {
          if (!pulls) {
            pulls++;
            sink(deriving.push(0));
          }
        } else if (tb === deriving.close) {
          ending++;
        }
      }));
    };

    const array = sinks.toArray(source);
    expect(array).toEqual([0]);
    expect(ending).toBe(1);
  });
});

describe('toPromise', () => {
  it('creates a Promise that resolves on the last value', async () => {
    let pulls = 0;
    let sink = null;

    const source: types.sourceT<any> = _sink => {
      sink = _sink;
      sink(deriving.start(tb => {
        if (tb === deriving.pull)
          pulls++;
      }));
    };

    const fn = jest.fn();
    const promise = web.toPromise(source).then(fn);

    expect(pulls).toBe(1);
    sink(deriving.push(0));
    expect(pulls).toBe(2);
    sink(deriving.push(1));
    sink(deriving.end());
    expect(fn).not.toHaveBeenCalled();

    await promise;
    expect(fn).toHaveBeenCalledWith(1);
  });

  it('creates a Promise for synchronous sources', async () => {
    const fn = jest.fn();
    await web.toPromise(sources.fromArray([1, 2, 3])).then(fn);
    expect(fn).toHaveBeenCalledWith(3);
  });
});

describe('toObservable', () => {
  it('creates an Observable mirroring the Wonka source', () => {
    const next = jest.fn();
    const complete = jest.fn();
    let pulls = 0;
    let sink = null;

    const source: types.sourceT<any> = _sink => {
      sink = _sink;
      sink(deriving.start(tb => {
        if (tb === deriving.pull)
          pulls++;
      }));
    };

    Observable.from(web.toObservable(source) as any).subscribe({
      next,
      complete,
    });

    expect(pulls).toBe(1);
    sink(deriving.push(0));
    expect(next).toHaveBeenCalledWith(0);
    sink(deriving.push(1));
    expect(next).toHaveBeenCalledWith(1);
    sink(deriving.end());
    expect(complete).toHaveBeenCalled();
  });

  it('forwards cancellations from the Observable as a talkback', () => {
    let ending = 0;
    const source: types.sourceT<any> = sink =>
      sink(deriving.start(tb => {
        if (tb === deriving.close)
          ending++;
      }));

    const sub = Observable.from(web.toObservable(source) as any).subscribe({});

    expect(ending).toBe(0);
    sub.unsubscribe();
    expect(ending).toBe(1);
  });
});

describe('toCallbag', () => {
  it('creates a Callbag mirroring the Wonka source', () => {
    const fn = jest.fn();
    let pulls = 0;
    let sink = null;

    const source: types.sourceT<any> = _sink => {
      sink = _sink;
      sink(deriving.start(tb => {
        if (tb === deriving.pull)
          pulls++;
      }));
    };

    callbagIterate(fn)(web.toCallbag(source));

    expect(pulls).toBe(1);
    sink(deriving.push(0));
    expect(fn).toHaveBeenCalledWith(0);
    sink(deriving.push(1));
    expect(fn).toHaveBeenCalledWith(1);
    sink(deriving.end());
  });

  it('forwards cancellations from the Callbag as a talkback', () => {
    let ending = 0;
    const fn = jest.fn();

    const source: types.sourceT<any> = sink =>
      sink(deriving.start(tb => {
        if (tb === deriving.pull)
          sink(deriving.push(0));
        if (tb === deriving.close)
          ending++;
      }));

    callbagIterate(fn)(callbagTake(1)(web.toCallbag(source) as any));

    expect(fn.mock.calls).toEqual([[0]]);
    expect(ending).toBe(1);
  });
});
