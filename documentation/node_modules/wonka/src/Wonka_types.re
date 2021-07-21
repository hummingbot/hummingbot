/* A sink has the signature: `signalT('a) => unit`
 * A source thus has the signature: `sink => unit`, or `(signalT('a) => unit) => unit`
 *
 * Effectively a sink is a callback receiving signals as its first argument.
 * - Start(talkback) will be carrying a talkback using which the sink can attempt
 *   to pull values (Pull) or request the source to end its stream (End)
 * - Push(payload) carries a value that the source sends to the sink.
 *   This can happen at any time, since a source can be both pullable or
 *   merely listenable.
 * - End signifies the end of the source stream, be it because of a talkback (End)
 *   or because the source is exhausted.
 *
 * In detail, a talkback is simply a callback that receives a talkback signal as
 * its first argument. It's thus typically anonymously created by the source.
 *
 * A source is a factory that accepts a sink. Calling a source with a sink will
 * instantiate and initiate the source's stream, after which the source sends the sink
 * a talkback (Start(talkback)). This is called the "handshake".
 *
 * Typically an operator factory won't call the source with a sink it receives
 * immediately—because this would cause the operator to simply be a noop—but instead
 * it will create an intermediate sink with the same signature to perform its own
 * logic.
 *
 * At that point the operator can for instance intercept the talkback for its own
 * purposes, or call the actual sink as it sees fit.
 */

[@genType.import "./shims/Js.shim"]
type talkbackT =
  | Pull
  | Close;

[@genType.import "./shims/Js.shim"]
type signalT('a) =
  | Start((. talkbackT) => unit)
  | Push('a)
  | End;

[@genType]
type sinkT('a) = (. signalT('a)) => unit;

[@genType]
type sourceT('a) = sinkT('a) => unit;

[@genType]
type operatorT('a, 'b) = sourceT('a) => sourceT('b);

[@genType]
type teardownT = (. unit) => unit;

[@genType]
type subscriptionT = {unsubscribe: unit => unit};

[@genType]
type observerT('a) = {
  next: 'a => unit,
  complete: unit => unit,
};

[@genType]
type subjectT('a) = {
  source: sourceT('a),
  next: 'a => unit,
  complete: unit => unit,
};

/* Sinks and sources need to explicitly be their own callbacks;
 * This means that currying needs to be forced for Bucklescript
 * not to optimise them away
 */
external curry: 'a => 'a = "%identity";
