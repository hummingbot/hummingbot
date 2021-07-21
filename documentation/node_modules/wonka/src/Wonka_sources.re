open Wonka_types;
open Wonka_helpers;

type trampolineT('a) = {
  mutable ended: bool,
  mutable looping: bool,
  mutable pulled: bool,
  mutable current: 'a,
};

[@genType]
let fromArray = (arr: array('a)): sourceT('a) =>
  curry(sink => {
    let size = Rebel.Array.size(arr);
    let state = {ended: false, looping: false, pulled: false, current: 0};

    sink(.
      Start(
        (. signal) =>
          switch (signal, state.looping) {
          | (Pull, false) =>
            state.pulled = true;
            state.looping = true;

            while (state.pulled && !state.ended) {
              if (state.current < size) {
                let x = Rebel.Array.getUnsafe(arr, state.current);
                state.current = state.current + 1;
                state.pulled = false;
                sink(. Push(x));
              } else {
                state.ended = true;
                sink(. End);
              };
            };

            state.looping = false;
          | (Pull, true) => state.pulled = true
          | (Close, _) => state.ended = true
          },
      ),
    );
  });

[@genType]
let fromList = (ls: list('a)): sourceT('a) =>
  curry(sink => {
    let state = {ended: false, looping: false, pulled: false, current: ls};

    sink(.
      Start(
        (. signal) =>
          switch (signal, state.looping) {
          | (Pull, false) =>
            state.pulled = true;
            state.looping = true;

            while (state.pulled && !state.ended) {
              switch (state.current) {
              | [x, ...rest] =>
                state.current = rest;
                state.pulled = false;
                sink(. Push(x));
              | [] =>
                state.ended = true;
                sink(. End);
              };
            };

            state.looping = false;
          | (Pull, true) => state.pulled = true
          | (Close, _) => state.ended = true
          },
      ),
    );
  });

[@genType]
let fromValue = (x: 'a): sourceT('a) =>
  curry(sink => {
    let ended = ref(false);

    sink(.
      Start(
        (. signal) =>
          switch (signal) {
          | Pull when ! ended^ =>
            ended := true;
            sink(. Push(x));
            sink(. End);
          | Pull => ()
          | Close => ended := true
          },
      ),
    );
  });

type makeStateT = {
  mutable teardown: (. unit) => unit,
  mutable ended: bool,
};

[@genType]
let make = (f: (. observerT('a)) => teardownT): sourceT('a) =>
  curry(sink => {
    let state: makeStateT = {teardown: (.) => (), ended: false};

    state.teardown =
      f(. {
        next: value =>
          if (!state.ended) {
            sink(. Push(value));
          },
        complete: () =>
          if (!state.ended) {
            state.ended = true;
            sink(. End);
          },
      });

    sink(.
      Start(
        (. signal) =>
          switch (signal) {
          | Close when !state.ended =>
            state.ended = true;
            state.teardown(.);
          | _ => ()
          },
      ),
    );
  });

type subjectState('a) = {
  mutable sinks: Rebel.Array.t(sinkT('a)),
  mutable ended: bool,
};

[@genType]
let makeSubject = (): subjectT('a) => {
  let state: subjectState('a) = {
    sinks: Rebel.Array.makeEmpty(),
    ended: false,
  };

  let source = sink => {
    state.sinks = Rebel.Array.append(state.sinks, sink);
    sink(.
      Start(
        (. signal) =>
          switch (signal) {
          | Close =>
            state.sinks = Rebel.Array.filter(state.sinks, x => x !== sink)
          | _ => ()
          },
      ),
    );
  };

  let next = value =>
    if (!state.ended) {
      Rebel.Array.forEach(state.sinks, sink => sink(. Push(value)));
    };

  let complete = () =>
    if (!state.ended) {
      state.ended = true;
      Rebel.Array.forEach(state.sinks, sink => sink(. End));
    };

  {source, next, complete};
};

[@genType]
let empty = (sink: sinkT('a)): unit => {
  let ended = ref(false);
  sink(.
    Start(
      (. signal) => {
        switch (signal) {
        | Close => ended := true
        | Pull when ! ended^ => sink(. End)
        | _ => ()
        }
      },
    ),
  );
};

[@genType]
let never = (sink: sinkT('a)): unit => {
  sink(. Start(talkbackPlaceholder));
};
