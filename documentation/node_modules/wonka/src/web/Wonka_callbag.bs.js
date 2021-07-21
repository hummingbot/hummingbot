

import * as Block from "bs-platform/lib/es6/block.js";
import * as Curry from "bs-platform/lib/es6/curry.js";

function fromCallbag(callbag) {
  return (function (sink) {
      var wrappedSink = function (signal, data) {
        switch (signal) {
          case /* CALLBAG_START */0 :
              var wrappedTalkback = function (talkbackSignal) {
                if (talkbackSignal) {
                  return data(/* CALLBAG_END */2);
                } else {
                  return data(/* CALLBAG_DATA */1);
                }
              };
              return sink(/* Start */Block.__(0, [wrappedTalkback]));
          case /* CALLBAG_DATA */1 :
              return sink(/* Push */Block.__(1, [data]));
          case /* CALLBAG_END */2 :
              return sink(/* End */0);
          
        }
      };
      return Curry._2(callbag, /* CALLBAG_START */0, wrappedSink);
    });
}

function toCallbag(source) {
  return (function (signal, data) {
      if (signal === /* CALLBAG_START */0) {
        return Curry._1(source, (function (signal) {
                      if (typeof signal === "number") {
                        return Curry._2(data, /* CALLBAG_END */2, undefined);
                      }
                      if (signal.tag) {
                        return Curry._2(data, /* CALLBAG_DATA */1, signal[0]);
                      }
                      var talkbackFn = signal[0];
                      var wrappedTalkbackFn = function (talkback) {
                        switch (talkback) {
                          case /* CALLBAG_START */0 :
                              return ;
                          case /* CALLBAG_DATA */1 :
                              return talkbackFn(/* Pull */0);
                          case /* CALLBAG_END */2 :
                              return talkbackFn(/* Close */1);
                          
                        }
                      };
                      return Curry._2(data, /* CALLBAG_START */0, wrappedTalkbackFn);
                    }));
      }
      
    });
}

export {
  fromCallbag ,
  toCallbag ,
  
}
/* No side effect */
