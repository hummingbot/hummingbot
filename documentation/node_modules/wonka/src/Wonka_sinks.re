open Wonka_types;
open Wonka_helpers;

type subscribeStateT = {
  mutable talkback: (. talkbackT) => unit,
  mutable ended: bool,
};

[@genType]
type subscribeConsumerT('a) = sourceT('a) => subscriptionT;

[@genType]
let subscribe = (f: (. 'a) => unit): subscribeConsumerT('a) =>
  curry(source => {
    let state: subscribeStateT = {
      talkback: talkbackPlaceholder,
      ended: false,
    };

    source((. signal) =>
      switch (signal) {
      | Start(x) =>
        state.talkback = x;
        x(. Pull);
      | Push(x) when !state.ended =>
        f(. x);
        state.talkback(. Pull);
      | Push(_) => ()
      | End => state.ended = true
      }
    );

    {
      unsubscribe: () =>
        if (!state.ended) {
          state.ended = true;
          state.talkback(. Close);
        },
    };
  });

[@genType]
type forEachConsumerT('a) = sourceT('a) => unit;

[@genType]
let forEach = (f: (. 'a) => unit): forEachConsumerT('a) =>
  curry(source => ignore(subscribe(f, source)));

[@genType]
let publish = (source: sourceT('a)): subscriptionT =>
  subscribe((. _) => (), source);

type toArrayStateT('a) = {
  values: Rebel.MutableQueue.t('a),
  mutable talkback: (. talkbackT) => unit,
  mutable value: option('a),
  mutable ended: bool,
};

[@genType]
let toArray = (source: sourceT('a)): array('a) => {
  let state: toArrayStateT('a) = {
    values: Rebel.MutableQueue.make(),
    talkback: talkbackPlaceholder,
    value: None,
    ended: false,
  };

  source((. signal) =>
    switch (signal) {
    | Start(x) =>
      state.talkback = x;
      x(. Pull);
    | Push(value) =>
      Rebel.MutableQueue.add(state.values, value);
      state.talkback(. Pull);
    | End => state.ended = true
    }
  );

  if (!state.ended) {
    state.talkback(. Close);
  };

  Rebel.MutableQueue.toArray(state.values);
};
