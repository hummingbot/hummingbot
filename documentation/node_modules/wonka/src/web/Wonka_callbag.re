open Wonka_types;

[@genType]
type callbagSignal =
  | [@genType.as 0] CALLBAG_START /* 0 */
  | [@genType.as 1] CALLBAG_DATA /* 1 */
  | [@genType.as 2] CALLBAG_END /* 2 */;

[@genType]
type callbagData('a);

[@genType]
type callbagTalkback = (. callbagSignal) => unit;

[@genType.import "../shims/Js.shim"]
type callbagT('a) = (callbagSignal, callbagData('a)) => unit;

external unsafe_getCallbag: callbagData('a) => callbagT('a) = "%identity";
external unsafe_getTalkback: callbagData('a) => callbagTalkback = "%identity";
external unsafe_getValue: callbagData('a) => 'a = "%identity";
external unsafe_wrap: 'any => callbagData('a) = "%identity";

[@genType]
let fromCallbag = (callbag: callbagT('a)): sourceT('a) =>
  curry(sink => {
    let wrappedSink =
      (. signal, data) =>
        switch (signal) {
        | CALLBAG_START =>
          let talkback = unsafe_getTalkback(data);
          let wrappedTalkback = (
            (. talkbackSignal: talkbackT) =>
              switch (talkbackSignal) {
              | Pull => talkback(. CALLBAG_DATA)
              | Close => talkback(. CALLBAG_END)
              }
          );
          sink(. Start(wrappedTalkback));
        | CALLBAG_DATA => sink(. Push(unsafe_getValue(data)))
        | CALLBAG_END => sink(. End)
        };
    callbag(CALLBAG_START, unsafe_wrap(wrappedSink));
  });

[@genType]
let toCallbag = (source: sourceT('a)): callbagT('a) =>
  curry((signal, data) =>
    if (signal === CALLBAG_START) {
      let callbag = unsafe_getCallbag(data);
      source((. signal) =>
        switch (signal) {
        | Start(talkbackFn) =>
          let wrappedTalkbackFn = (talkback: callbagSignal) =>
            switch (talkback) {
            | CALLBAG_START => ()
            | CALLBAG_DATA => talkbackFn(. Pull)
            | CALLBAG_END => talkbackFn(. Close)
            };
          callbag(CALLBAG_START, unsafe_wrap(wrappedTalkbackFn));
        | Push(data) => callbag(CALLBAG_DATA, unsafe_wrap(data))
        | End => callbag(CALLBAG_END, unsafe_wrap())
        }
      );
    }
  );
