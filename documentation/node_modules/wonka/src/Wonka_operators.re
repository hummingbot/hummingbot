open Wonka_types;
open Wonka_helpers;

type bufferStateT('a) = {
  mutable buffer: Rebel.MutableQueue.t('a),
  mutable sourceTalkback: (. talkbackT) => unit,
  mutable notifierTalkback: (. talkbackT) => unit,
  mutable pulled: bool,
  mutable ended: bool,
};

[@genType]
let buffer = (notifier: sourceT('a)): operatorT('b, array('b)) =>
  curry(source =>
    curry(sink => {
      let state = {
        buffer: Rebel.MutableQueue.make(),
        sourceTalkback: talkbackPlaceholder,
        notifierTalkback: talkbackPlaceholder,
        pulled: false,
        ended: false,
      };

      source((. signal) => {
        switch (signal) {
        | Start(tb) =>
          state.sourceTalkback = tb;

          notifier((. signal) => {
            switch (signal) {
            | Start(tb) => state.notifierTalkback = tb
            | Push(_) when !state.ended =>
              if (Rebel.MutableQueue.size(state.buffer) > 0) {
                let buffer = state.buffer;
                state.buffer = Rebel.MutableQueue.make();
                sink(. Push(Rebel.MutableQueue.toArray(buffer)));
              }
            | Push(_) => ()
            | End when !state.ended =>
              state.ended = true;
              state.sourceTalkback(. Close);
              if (Rebel.MutableQueue.size(state.buffer) > 0) {
                sink(. Push(Rebel.MutableQueue.toArray(state.buffer)));
              };
              sink(. End);
            | End => ()
            };
            ();
          });
        | Push(value) when !state.ended =>
          Rebel.MutableQueue.add(state.buffer, value);
          if (!state.pulled) {
            state.pulled = true;
            state.sourceTalkback(. Pull);
            state.notifierTalkback(. Pull);
          } else {
            state.pulled = false;
          };
        | Push(_) => ()
        | End when !state.ended =>
          state.ended = true;
          state.notifierTalkback(. Close);
          if (Rebel.MutableQueue.size(state.buffer) > 0) {
            sink(. Push(Rebel.MutableQueue.toArray(state.buffer)));
          };
          sink(. End);
        | End => ()
        };
        ();
      });

      sink(.
        Start(
          (. signal) =>
            if (!state.ended) {
              switch (signal) {
              | Close =>
                state.ended = true;
                state.sourceTalkback(. Close);
                state.notifierTalkback(. Close);
              | Pull when !state.pulled =>
                state.pulled = true;
                state.sourceTalkback(. Pull);
                state.notifierTalkback(. Pull);
              | Pull => ()
              };
            },
        ),
      );
    })
  );

type combineStateT('a, 'b) = {
  mutable talkbackA: (. talkbackT) => unit,
  mutable talkbackB: (. talkbackT) => unit,
  mutable lastValA: option('a),
  mutable lastValB: option('b),
  mutable gotSignal: bool,
  mutable endCounter: int,
  mutable ended: bool,
};

[@genType]
let combine =
    (sourceA: sourceT('a), sourceB: sourceT('b)): sourceT(('a, 'b)) =>
  curry(sink => {
    let state = {
      talkbackA: talkbackPlaceholder,
      talkbackB: talkbackPlaceholder,
      lastValA: None,
      lastValB: None,
      gotSignal: false,
      endCounter: 0,
      ended: false,
    };

    sourceA((. signal) =>
      switch (signal, state.lastValB) {
      | (Start(tb), _) => state.talkbackA = tb
      | (Push(a), None) =>
        state.lastValA = Some(a);
        if (!state.gotSignal) {
          state.talkbackB(. Pull);
        } else {
          state.gotSignal = false;
        };
      | (Push(a), Some(b)) when !state.ended =>
        state.lastValA = Some(a);
        state.gotSignal = false;
        sink(. Push((a, b)));
      | (End, _) when state.endCounter < 1 =>
        state.endCounter = state.endCounter + 1
      | (End, _) when !state.ended =>
        state.ended = true;
        sink(. End);
      | _ => ()
      }
    );

    sourceB((. signal) =>
      switch (signal, state.lastValA) {
      | (Start(tb), _) => state.talkbackB = tb
      | (Push(b), None) =>
        state.lastValB = Some(b);
        if (!state.gotSignal) {
          state.talkbackA(. Pull);
        } else {
          state.gotSignal = false;
        };
      | (Push(b), Some(a)) when !state.ended =>
        state.lastValB = Some(b);
        state.gotSignal = false;
        sink(. Push((a, b)));
      | (End, _) when state.endCounter < 1 =>
        state.endCounter = state.endCounter + 1
      | (End, _) when !state.ended =>
        state.ended = true;
        sink(. End);
      | _ => ()
      }
    );

    sink(.
      Start(
        (. signal) =>
          if (!state.ended) {
            switch (signal) {
            | Close =>
              state.ended = true;
              state.talkbackA(. Close);
              state.talkbackB(. Close);
            | Pull when !state.gotSignal =>
              state.gotSignal = true;
              state.talkbackA(. signal);
              state.talkbackB(. signal);
            | Pull => ()
            };
          },
      ),
    );
  });

type concatMapStateT('a) = {
  inputQueue: Rebel.MutableQueue.t('a),
  mutable outerTalkback: (. talkbackT) => unit,
  mutable outerPulled: bool,
  mutable innerTalkback: (. talkbackT) => unit,
  mutable innerActive: bool,
  mutable innerPulled: bool,
  mutable ended: bool,
};

[@genType]
let concatMap = (f: (. 'a) => sourceT('b)): operatorT('a, 'b) =>
  curry(source =>
    curry(sink => {
      let state: concatMapStateT('a) = {
        inputQueue: Rebel.MutableQueue.make(),
        outerTalkback: talkbackPlaceholder,
        outerPulled: false,
        innerTalkback: talkbackPlaceholder,
        innerActive: false,
        innerPulled: false,
        ended: false,
      };

      let rec applyInnerSource = innerSource => {
        state.innerActive = true;
        innerSource((. signal) => {
          switch (signal) {
          | Start(tb) =>
            state.innerTalkback = tb;
            state.innerPulled = false;
            tb(. Pull);
          | Push(_) when state.innerActive =>
            sink(. signal);
            if (!state.innerPulled) {
              state.innerTalkback(. Pull);
            } else {
              state.innerPulled = false;
            };
          | Push(_) => ()
          | End when state.innerActive =>
            state.innerActive = false;
            switch (Rebel.MutableQueue.pop(state.inputQueue)) {
            | Some(input) => applyInnerSource(f(. input))
            | None when state.ended => sink(. End)
            | None when !state.outerPulled =>
              state.outerPulled = true;
              state.outerTalkback(. Pull);
            | None => ()
            };
          | End => ()
          };
          ();
        });
        ();
      };

      source((. signal) => {
        switch (signal) {
        | Start(tb) => state.outerTalkback = tb
        | Push(x) when !state.ended =>
          state.outerPulled = false;
          if (state.innerActive) {
            Rebel.MutableQueue.add(state.inputQueue, x);
          } else {
            applyInnerSource(f(. x));
          };
        | Push(_) => ()
        | End when !state.ended =>
          state.ended = true;
          if (!state.innerActive
              && Rebel.MutableQueue.isEmpty(state.inputQueue)) {
            sink(. End);
          };
        | End => ()
        };
        ();
      });

      sink(.
        Start(
          (. signal) =>
            switch (signal) {
            | Pull =>
              if (!state.ended && !state.outerPulled) {
                state.outerPulled = true;
                state.outerTalkback(. Pull);
              };
              if (state.innerActive && !state.innerPulled) {
                state.innerPulled = true;
                state.innerTalkback(. Pull);
              };
            | Close =>
              if (!state.ended) {
                state.ended = true;
                state.outerTalkback(. Close);
              };
              if (state.innerActive) {
                state.innerActive = false;
                state.innerTalkback(. Close);
              };
            },
        ),
      );
    })
  );

[@genType]
let concatAll = (source: sourceT(sourceT('a))): sourceT('a) =>
  concatMap((. x) => x, source);

[@genType]
let concat = (sources: array(sourceT('a))): sourceT('a) =>
  concatMap((. x) => x, Wonka_sources.fromArray(sources));

[@genType]
let filter = (f: (. 'a) => bool): operatorT('a, 'a) =>
  curry(source =>
    curry(sink => {
      let talkback = ref(talkbackPlaceholder);

      source((. signal) => {
        switch (signal) {
        | Start(tb) =>
          talkback := tb;
          sink(. signal);
        | Push(x) when !f(. x) => talkback^(. Pull)
        | _ => sink(. signal)
        };
        ();
      });
    })
  );

[@genType]
let map = (f: (. 'a) => 'b): operatorT('a, 'b) =>
  curry(source =>
    curry(sink =>
      source((. signal) => {
        sink(.
          /* The signal needs to be recreated for genType to generate
             the correct generics during codegen */
          switch (signal) {
          | Start(x) => Start(x)
          | Push(x) => Push(f(. x))
          | End => End
          },
        )
      })
    )
  );

type mergeMapStateT = {
  mutable outerTalkback: (. talkbackT) => unit,
  mutable outerPulled: bool,
  mutable innerTalkbacks: Rebel.Array.t((. talkbackT) => unit),
  mutable ended: bool,
};

[@genType]
let mergeMap = (f: (. 'a) => sourceT('b)): operatorT('a, 'b) =>
  curry(source =>
    curry(sink => {
      let state: mergeMapStateT = {
        outerTalkback: talkbackPlaceholder,
        outerPulled: false,
        innerTalkbacks: Rebel.Array.makeEmpty(),
        ended: false,
      };

      let applyInnerSource = innerSource => {
        let talkback = ref(talkbackPlaceholder);

        innerSource((. signal) =>
          switch (signal) {
          | Start(tb) =>
            talkback := tb;
            state.innerTalkbacks =
              Rebel.Array.append(state.innerTalkbacks, tb);
            tb(. Pull);
          | Push(x) when Rebel.Array.size(state.innerTalkbacks) !== 0 =>
            sink(. Push(x));
            talkback^(. Pull);
          | Push(_) => ()
          | End when Rebel.Array.size(state.innerTalkbacks) !== 0 =>
            state.innerTalkbacks =
              Rebel.Array.filter(state.innerTalkbacks, x => x !== talkback^);
            let exhausted = Rebel.Array.size(state.innerTalkbacks) === 0;
            if (state.ended && exhausted) {
              sink(. End);
            } else if (!state.outerPulled && exhausted) {
              state.outerPulled = true;
              state.outerTalkback(. Pull);
            };
          | End => ()
          }
        );
      };

      source((. signal) =>
        switch (signal) {
        | Start(tb) => state.outerTalkback = tb
        | Push(x) when !state.ended =>
          state.outerPulled = false;
          applyInnerSource(f(. x));
          if (!state.outerPulled) {
            state.outerPulled = true;
            state.outerTalkback(. Pull);
          };
        | Push(_) => ()
        | End when !state.ended =>
          state.ended = true;
          if (Rebel.Array.size(state.innerTalkbacks) === 0) {
            sink(. End);
          };
        | End => ()
        }
      );

      sink(.
        Start(
          (. signal) =>
            switch (signal) {
            | Close =>
              if (!state.ended) {
                state.ended = true;
                state.outerTalkback(. signal);
              };

              Rebel.Array.forEach(state.innerTalkbacks, tb => tb(. signal));
              state.innerTalkbacks = Rebel.Array.makeEmpty();
            | Pull =>
              if (!state.outerPulled && !state.ended) {
                state.outerPulled = true;
                state.outerTalkback(. Pull);
              } else {
                state.outerPulled = false;
              };

              Rebel.Array.forEach(state.innerTalkbacks, tb => tb(. Pull));
            },
        ),
      );
    })
  );

[@genType]
let merge = (sources: array(sourceT('a))): sourceT('a) =>
  mergeMap((. x) => x, Wonka_sources.fromArray(sources));

[@genType]
let mergeAll = (source: sourceT(sourceT('a))): sourceT('a) =>
  mergeMap((. x) => x, source);

[@genType]
let flatten = mergeAll;

[@genType]
let onEnd = (f: (. unit) => unit): operatorT('a, 'a) =>
  curry(source =>
    curry(sink => {
      let ended = ref(false);
      source((. signal) =>
        switch (signal) {
        | Start(talkback) =>
          sink(.
            Start(
              (. signal) =>
                if (! ended^) {
                  switch (signal) {
                  | Pull => talkback(. signal)
                  | Close =>
                    ended := true;
                    talkback(. signal);
                    f(.);
                  };
                },
            ),
          )
        | Push(_) when ! ended^ => sink(. signal)
        | Push(_) => ()
        | End when ! ended^ =>
          ended := true;
          sink(. signal);
          f(.);
        | End => ()
        }
      );
    })
  );

[@genType]
let onPush = (f: (. 'a) => unit): operatorT('a, 'a) =>
  curry(source =>
    curry(sink => {
      let ended = ref(false);
      source((. signal) => {
        switch (signal) {
        | Start(talkback) =>
          sink(.
            Start(
              (. signal) =>
                if (! ended^) {
                  switch (signal) {
                  | Pull => talkback(. signal)
                  | Close =>
                    ended := true;
                    talkback(. signal);
                  };
                },
            ),
          )
        | Push(x) when ! ended^ =>
          f(. x);
          sink(. signal);
        | Push(_) => ()
        | End when ! ended^ =>
          ended := true;
          sink(. signal);
        | End => ()
        };
        ();
      });
    })
  );

[@genType]
let tap = onPush;

[@genType]
let onStart = (f: (. unit) => unit): operatorT('a, 'a) =>
  curry(source =>
    curry(sink =>
      source((. signal) =>
        switch (signal) {
        | Start(_) =>
          sink(. signal);
          f(.);
        | _ => sink(. signal)
        }
      )
    )
  );

type sampleStateT('a) = {
  mutable sourceTalkback: (. talkbackT) => unit,
  mutable notifierTalkback: (. talkbackT) => unit,
  mutable value: option('a),
  mutable pulled: bool,
  mutable ended: bool,
};

[@genType]
let sample = (notifier: sourceT('a)): operatorT('b, 'b) =>
  curry(source =>
    curry(sink => {
      let state = {
        sourceTalkback: talkbackPlaceholder,
        notifierTalkback: talkbackPlaceholder,
        value: None,
        pulled: false,
        ended: false,
      };

      source((. signal) =>
        switch (signal) {
        | Start(tb) => state.sourceTalkback = tb
        | Push(x) =>
          state.value = Some(x);
          if (!state.pulled) {
            state.pulled = true;
            state.notifierTalkback(. Pull);
            state.sourceTalkback(. Pull);
          } else {
            state.pulled = false;
          };
        | End when !state.ended =>
          state.ended = true;
          state.notifierTalkback(. Close);
          sink(. End);
        | End => ()
        }
      );

      notifier((. signal) =>
        switch (signal, state.value) {
        | (Start(tb), _) => state.notifierTalkback = tb
        | (End, _) when !state.ended =>
          state.ended = true;
          state.sourceTalkback(. Close);
          sink(. End);
        | (End, _) => ()
        | (Push(_), Some(x)) when !state.ended =>
          state.value = None;
          sink(. Push(x));
        | (Push(_), _) => ()
        }
      );

      sink(.
        Start(
          (. signal) =>
            if (!state.ended) {
              switch (signal) {
              | Pull when !state.pulled =>
                state.pulled = true;
                state.sourceTalkback(. Pull);
                state.notifierTalkback(. Pull);
              | Pull => ()
              | Close =>
                state.ended = true;
                state.sourceTalkback(. Close);
                state.notifierTalkback(. Close);
              };
            },
        ),
      );
    })
  );

[@genType]
let scan = (f: (. 'acc, 'a) => 'acc, seed: 'acc): operatorT('a, 'acc) =>
  curry(source =>
    curry(sink => {
      let acc = ref(seed);

      source((. signal) =>
        sink(.
          switch (signal) {
          | Push(x) =>
            acc := f(. acc^, x);
            Push(acc^);
          | Start(x) => Start(x)
          | End => End
          },
        )
      );
    })
  );

type shareStateT('a) = {
  mutable sinks: Rebel.Array.t(sinkT('a)),
  mutable talkback: (. talkbackT) => unit,
  mutable gotSignal: bool,
};

[@genType]
let share = (source: sourceT('a)): sourceT('a) => {
  let state = {
    sinks: Rebel.Array.makeEmpty(),
    talkback: talkbackPlaceholder,
    gotSignal: false,
  };

  sink => {
    state.sinks = Rebel.Array.append(state.sinks, sink);

    if (Rebel.Array.size(state.sinks) === 1) {
      source((. signal) =>
        switch (signal) {
        | Push(_) =>
          state.gotSignal = false;
          Rebel.Array.forEach(state.sinks, sink => sink(. signal));
        | Start(x) => state.talkback = x
        | End =>
          Rebel.Array.forEach(state.sinks, sink => sink(. End));
          state.sinks = Rebel.Array.makeEmpty();
        }
      );
    };

    sink(.
      Start(
        (. signal) =>
          switch (signal) {
          | Close =>
            state.sinks = Rebel.Array.filter(state.sinks, x => x !== sink);
            if (Rebel.Array.size(state.sinks) === 0) {
              state.talkback(. Close);
            };
          | Pull when !state.gotSignal =>
            state.gotSignal = true;
            state.talkback(. signal);
          | Pull => ()
          },
      ),
    );
  };
};

type skipStateT = {
  mutable talkback: (. talkbackT) => unit,
  mutable rest: int,
};

[@genType]
let skip = (wait: int): operatorT('a, 'a) =>
  curry(source =>
    curry(sink => {
      let state: skipStateT = {talkback: talkbackPlaceholder, rest: wait};

      source((. signal) =>
        switch (signal) {
        | Start(tb) =>
          state.talkback = tb;
          sink(. signal);
        | Push(_) when state.rest > 0 =>
          state.rest = state.rest - 1;
          state.talkback(. Pull);
        | _ => sink(. signal)
        }
      );
    })
  );

type skipUntilStateT = {
  mutable sourceTalkback: (. talkbackT) => unit,
  mutable notifierTalkback: (. talkbackT) => unit,
  mutable skip: bool,
  mutable pulled: bool,
  mutable ended: bool,
};

[@genType]
let skipUntil = (notifier: sourceT('a)): operatorT('b, 'b) =>
  curry(source =>
    curry(sink => {
      let state: skipUntilStateT = {
        sourceTalkback: talkbackPlaceholder,
        notifierTalkback: talkbackPlaceholder,
        skip: true,
        pulled: false,
        ended: false,
      };

      source((. signal) => {
        switch (signal) {
        | Start(tb) =>
          state.sourceTalkback = tb;

          notifier((. signal) => {
            switch (signal) {
            | Start(innerTb) =>
              state.notifierTalkback = innerTb;
              innerTb(. Pull);
            | Push(_) =>
              state.skip = false;
              state.notifierTalkback(. Close);
            | End when state.skip =>
              state.ended = true;
              state.sourceTalkback(. Close);
            | End => ()
            };
            ();
          });
        | Push(_) when !state.skip && !state.ended =>
          state.pulled = false;
          sink(. signal);
        | Push(_) when !state.pulled =>
          state.pulled = true;
          state.sourceTalkback(. Pull);
          state.notifierTalkback(. Pull);
        | Push(_) => state.pulled = false
        | End =>
          if (state.skip) {
            state.notifierTalkback(. Close);
          };
          state.ended = true;
          sink(. End);
        };
        ();
      });

      sink(.
        Start(
          (. signal) =>
            if (!state.ended) {
              switch (signal) {
              | Close =>
                state.ended = true;
                state.sourceTalkback(. Close);
                if (state.skip) {
                  state.notifierTalkback(. Close);
                };
              | Pull when !state.pulled =>
                state.pulled = true;
                if (state.skip) {
                  state.notifierTalkback(. Pull);
                };
                state.sourceTalkback(. Pull);
              | Pull => ()
              };
            },
        ),
      );
    })
  );

type skipWhileStateT = {
  mutable talkback: (. talkbackT) => unit,
  mutable skip: bool,
};

[@genType]
let skipWhile = (f: (. 'a) => bool): operatorT('a, 'a) =>
  curry(source =>
    curry(sink => {
      let state: skipWhileStateT = {
        talkback: talkbackPlaceholder,
        skip: true,
      };

      source((. signal) =>
        switch (signal) {
        | Start(tb) =>
          state.talkback = tb;
          sink(. signal);
        | Push(x) when state.skip =>
          if (f(. x)) {
            state.talkback(. Pull);
          } else {
            state.skip = false;
            sink(. signal);
          }
        | _ => sink(. signal)
        }
      );
    })
  );

type switchMapStateT('a) = {
  mutable outerTalkback: (. talkbackT) => unit,
  mutable outerPulled: bool,
  mutable innerTalkback: (. talkbackT) => unit,
  mutable innerActive: bool,
  mutable innerPulled: bool,
  mutable ended: bool,
};

[@genType]
let switchMap = (f: (. 'a) => sourceT('b)): operatorT('a, 'b) =>
  curry(source =>
    curry(sink => {
      let state: switchMapStateT('a) = {
        outerTalkback: talkbackPlaceholder,
        outerPulled: false,
        innerTalkback: talkbackPlaceholder,
        innerActive: false,
        innerPulled: false,
        ended: false,
      };

      let applyInnerSource = innerSource => {
        state.innerActive = true;
        innerSource((. signal) =>
          if (state.innerActive) {
            switch (signal) {
            | Start(tb) =>
              state.innerTalkback = tb;
              state.innerPulled = false;
              tb(. Pull);
            | Push(_) =>
              sink(. signal);
              if (!state.innerPulled) {
                state.innerTalkback(. Pull);
              } else {
                state.innerPulled = false;
              };
            | End =>
              state.innerActive = false;
              if (state.ended) {
                sink(. signal);
              } else if (!state.outerPulled) {
                state.outerPulled = true;
                state.outerTalkback(. Pull);
              };
            };
          }
        );
        ();
      };

      source((. signal) => {
        switch (signal) {
        | Start(tb) => state.outerTalkback = tb
        | Push(x) when !state.ended =>
          if (state.innerActive) {
            state.innerTalkback(. Close);
            state.innerTalkback = talkbackPlaceholder;
          };

          if (!state.outerPulled) {
            state.outerPulled = true;
            state.outerTalkback(. Pull);
          } else {
            state.outerPulled = false;
          };

          applyInnerSource(f(. x));
        | Push(_) => ()
        | End when !state.ended =>
          state.ended = true;
          if (!state.innerActive) {
            sink(. End);
          };
        | End => ()
        };
        ();
      });

      sink(.
        Start(
          (. signal) =>
            switch (signal) {
            | Pull =>
              if (!state.ended && !state.outerPulled) {
                state.outerPulled = true;
                state.outerTalkback(. Pull);
              };
              if (state.innerActive && !state.innerPulled) {
                state.innerPulled = true;
                state.innerTalkback(. Pull);
              };
            | Close =>
              if (!state.ended) {
                state.ended = true;
                state.outerTalkback(. Close);
              };
              if (state.innerActive) {
                state.innerActive = false;
                state.innerTalkback(. Close);
              };
            },
        ),
      );
    })
  );

[@genType]
let switchAll = (source: sourceT(sourceT('a))): sourceT('a) =>
  switchMap((. x) => x, source);

type takeStateT = {
  mutable ended: bool,
  mutable taken: int,
  mutable talkback: (. talkbackT) => unit,
};

[@genType]
let take = (max: int): operatorT('a, 'a) =>
  curry(source =>
    curry(sink => {
      let state: takeStateT = {
        ended: false,
        taken: 0,
        talkback: talkbackPlaceholder,
      };

      source((. signal) =>
        switch (signal) {
        | Start(tb) when max <= 0 =>
          state.ended = true;
          sink(. End);
          tb(. Close);
        | Start(tb) => state.talkback = tb
        | Push(_) when state.taken < max && !state.ended =>
          state.taken = state.taken + 1;
          sink(. signal);
          if (!state.ended && state.taken >= max) {
            state.ended = true;
            sink(. End);
            state.talkback(. Close);
          };
        | Push(_) => ()
        | End when !state.ended =>
          state.ended = true;
          sink(. End);
        | End => ()
        }
      );

      sink(.
        Start(
          (. signal) =>
            if (!state.ended) {
              switch (signal) {
              | Pull when state.taken < max => state.talkback(. Pull)
              | Pull => ()
              | Close =>
                state.ended = true;
                state.talkback(. Close);
              };
            },
        ),
      );
    })
  );

type takeLastStateT('a) = {
  mutable queue: Rebel.MutableQueue.t('a),
  mutable talkback: (. talkbackT) => unit,
};

[@genType]
let takeLast = (max: int): operatorT('a, 'a) =>
  curry(source =>
    curry(sink => {
      let state: takeLastStateT('a) = {
        queue: Rebel.MutableQueue.make(),
        talkback: talkbackPlaceholder,
      };

      source((. signal) => {
        switch (signal) {
        | Start(talkback) when max <= 0 =>
          talkback(. Close);
          Wonka_sources.empty(sink);
        | Start(talkback) =>
          state.talkback = talkback;
          talkback(. Pull);
        | Push(x) =>
          let size = Rebel.MutableQueue.size(state.queue);
          if (size >= max && max > 0) {
            ignore(Rebel.MutableQueue.pop(state.queue));
          };

          Rebel.MutableQueue.add(state.queue, x);
          state.talkback(. Pull);
        | End =>
          Wonka_sources.fromArray(
            Rebel.MutableQueue.toArray(state.queue),
            sink,
          )
        };
        ();
      });
    })
  );

type takeUntilStateT = {
  mutable ended: bool,
  mutable sourceTalkback: (. talkbackT) => unit,
  mutable notifierTalkback: (. talkbackT) => unit,
};

[@genType]
let takeUntil = (notifier: sourceT('a)): operatorT('b, 'b) =>
  curry(source =>
    curry(sink => {
      let state: takeUntilStateT = {
        ended: false,
        sourceTalkback: talkbackPlaceholder,
        notifierTalkback: talkbackPlaceholder,
      };

      source((. signal) => {
        switch (signal) {
        | Start(tb) =>
          state.sourceTalkback = tb;

          notifier((. signal) => {
            switch (signal) {
            | Start(innerTb) =>
              state.notifierTalkback = innerTb;
              innerTb(. Pull);
            | Push(_) =>
              state.ended = true;
              state.sourceTalkback(. Close);
              sink(. End);
            | End => ()
            };
            ();
          });
        | End when !state.ended =>
          state.ended = true;
          state.notifierTalkback(. Close);
          sink(. End);
        | End => ()
        | Push(_) when !state.ended => sink(. signal)
        | Push(_) => ()
        };
        ();
      });

      sink(.
        Start(
          (. signal) =>
            if (!state.ended) {
              switch (signal) {
              | Close =>
                state.ended = true;
                state.sourceTalkback(. Close);
                state.notifierTalkback(. Close);
              | Pull => state.sourceTalkback(. Pull)
              };
            },
        ),
      );
    })
  );

type takeWhileStateT = {
  mutable talkback: (. talkbackT) => unit,
  mutable ended: bool,
};

[@genType]
let takeWhile = (f: (. 'a) => bool): operatorT('a, 'a) =>
  curry(source =>
    curry(sink => {
      let state: takeWhileStateT = {
        talkback: talkbackPlaceholder,
        ended: false,
      };

      source((. signal) =>
        switch (signal) {
        | Start(tb) =>
          state.talkback = tb;
          sink(. signal);
        | End when !state.ended =>
          state.ended = true;
          sink(. End);
        | End => ()
        | Push(x) when !state.ended =>
          if (!f(. x)) {
            state.ended = true;
            sink(. End);
            state.talkback(. Close);
          } else {
            sink(. signal);
          }
        | Push(_) => ()
        }
      );
    })
  );
