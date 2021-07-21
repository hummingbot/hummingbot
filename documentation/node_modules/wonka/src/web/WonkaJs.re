open Wonka_types;

[@genType]
let fromObservable = Wonka_observable.fromObservable;
[@genType]
let toObservable = Wonka_observable.toObservable;

[@genType]
let fromCallbag = Wonka_callbag.fromCallbag;
[@genType]
let toCallbag = Wonka_callbag.toCallbag;

/* operators */

type debounceStateT = {
  mutable id: option(Js.Global.timeoutId),
  mutable deferredEnded: bool,
  mutable ended: bool,
};

[@genType]
let debounce = (f: (. 'a) => int): operatorT('a, 'a) =>
  curry(source =>
    curry(sink => {
      let state: debounceStateT = {
        id: None,
        deferredEnded: false,
        ended: false,
      };

      let clearTimeout = () =>
        switch (state.id) {
        | Some(timeoutId) =>
          state.id = None;
          Js.Global.clearTimeout(timeoutId);
        | None => ()
        };

      source((. signal) =>
        switch (signal) {
        | Start(tb) =>
          sink(.
            Start(
              (. signal) =>
                if (!state.ended) {
                  switch (signal) {
                  | Close =>
                    state.ended = true;
                    state.deferredEnded = false;
                    clearTimeout();
                    tb(. Close);
                  | Pull => tb(. Pull)
                  };
                },
            ),
          )
        | Push(x) when !state.ended =>
          clearTimeout();
          state.id =
            Some(
              Js.Global.setTimeout(
                () => {
                  state.id = None;
                  sink(. signal);
                  if (state.deferredEnded) {
                    sink(. End);
                  };
                },
                f(. x),
              ),
            );
        | Push(_) => ()
        | End when !state.ended =>
          state.ended = true;
          switch (state.id) {
          | Some(_) => state.deferredEnded = true
          | None => sink(. End)
          };
        | End => ()
        }
      );
    })
  );

[@genType]
let delay = (wait: int): operatorT('a, 'a) =>
  curry(source =>
    curry(sink => {
      let active = ref(0);

      source((. signal) =>
        switch (signal) {
        | Start(_) => sink(. signal)
        | _ =>
          active := active^ + 1;
          ignore(
            Js.Global.setTimeout(
              () =>
                if (active^ !== 0) {
                  active := active^ - 1;
                  sink(. signal);
                },
              wait,
            ),
          );
        }
      );
    })
  );

[@genType]
let throttle = (f: (. 'a) => int): operatorT('a, 'a) =>
  curry(source =>
    curry(sink => {
      let skip = ref(false);
      let id: ref(option(Js.Global.timeoutId)) = ref(None);
      let clearTimeout = () =>
        switch (id^) {
        | Some(timeoutId) => Js.Global.clearTimeout(timeoutId)
        | None => ()
        };

      source((. signal) =>
        switch (signal) {
        | Start(tb) =>
          sink(.
            Start(
              (. signal) =>
                switch (signal) {
                | Close =>
                  clearTimeout();
                  tb(. Close);
                | _ => tb(. signal)
                },
            ),
          )
        | End =>
          clearTimeout();
          sink(. End);
        | Push(x) when ! skip^ =>
          skip := true;
          clearTimeout();
          id :=
            Some(
              Js.Global.setTimeout(
                () => {
                  id := None;
                  skip := false;
                },
                f(. x),
              ),
            );
          sink(. signal);
        | Push(_) => ()
        }
      );
    })
  );

/* sinks */
[@genType]
let toPromise = (source: sourceT('a)): Js.Promise.t('a) => {
  Js.Promise.make((~resolve, ~reject as _) => {
    Wonka_operators.takeLast(1, source, (. signal) =>
      switch (signal) {
      | Start(x) => x(. Pull)
      | Push(x) => resolve(. x)
      | End => ()
      }
    );
    ();
  });
};

/* sources */
[@genType]
let interval = (p: int): sourceT(int) =>
  curry(sink => {
    let i = ref(0);
    let id =
      Js.Global.setInterval(
        () => {
          let num = i^;
          i := i^ + 1;
          sink(. Push(num));
        },
        p,
      );

    sink(.
      Start(
        (. signal) =>
          switch (signal) {
          | Close => Js.Global.clearInterval(id)
          | _ => ()
          },
      ),
    );
  });

[@genType]
let fromDomEvent = (element: Dom.element, event: string): sourceT(Dom.event) =>
  curry(sink => {
    let addEventListener: (Dom.element, string, Dom.event => unit) => unit = [%raw
      {|
    function (element, event, handler) {
      element.addEventListener(event, handler);
    }
  |}
    ];

    let removeEventListener: (Dom.element, string, Dom.event => unit) => unit = [%raw
      {|
    function (element, event, handler) {
      element.removeEventListener(event, handler);
    }
  |}
    ];

    let handler = event => sink(. Push(event));

    sink(.
      Start(
        (. signal) =>
          switch (signal) {
          | Close => removeEventListener(element, event, handler)
          | _ => ()
          },
      ),
    );

    addEventListener(element, event, handler);
  });

[@genType]
let fromPromise = (promise: Js.Promise.t('a)): sourceT('a) =>
  curry(sink => {
    let ended = ref(false);

    ignore(
      Js.Promise.then_(
        value => {
          if (! ended^) {
            sink(. Push(value));
            sink(. End);
          };

          Js.Promise.resolve();
        },
        promise,
      ),
    );

    sink(.
      Start(
        (. signal) =>
          switch (signal) {
          | Close => ended := true
          | _ => ()
          },
      ),
    );
  });
