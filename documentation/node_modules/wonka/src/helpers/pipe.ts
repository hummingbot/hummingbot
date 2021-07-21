import { sourceT as Source } from '../Wonka_types.gen';

interface UnaryFn<T, R> {
  (source: T): R;
}

/* pipe definitions for source + operators composition */

function pipe<T, A>(source: Source<T>, op1: UnaryFn<Source<T>, Source<A>>): Source<A>;

function pipe<T, A, B>(
  source: Source<T>,
  op1: UnaryFn<Source<T>, Source<A>>,
  op2: UnaryFn<Source<A>, Source<B>>
): Source<B>;

function pipe<T, A, B, C>(
  source: Source<T>,
  op1: UnaryFn<Source<T>, Source<A>>,
  op2: UnaryFn<Source<A>, Source<B>>,
  op3: UnaryFn<Source<B>, Source<C>>
): Source<C>;

function pipe<T, A, B, C, D>(
  source: Source<T>,
  op1: UnaryFn<Source<T>, Source<A>>,
  op2: UnaryFn<Source<A>, Source<B>>,
  op3: UnaryFn<Source<B>, Source<C>>,
  op4: UnaryFn<Source<C>, Source<D>>
): Source<D>;

function pipe<T, A, B, C, D, E>(
  source: Source<T>,
  op1: UnaryFn<Source<T>, Source<A>>,
  op2: UnaryFn<Source<A>, Source<B>>,
  op3: UnaryFn<Source<B>, Source<C>>,
  op4: UnaryFn<Source<C>, Source<D>>,
  op5: UnaryFn<Source<D>, Source<E>>
): Source<E>;

function pipe<T, A, B, C, D, E, F>(
  source: Source<T>,
  op1: UnaryFn<Source<T>, Source<A>>,
  op2: UnaryFn<Source<A>, Source<B>>,
  op3: UnaryFn<Source<B>, Source<C>>,
  op4: UnaryFn<Source<C>, Source<D>>,
  op5: UnaryFn<Source<D>, Source<E>>,
  op6: UnaryFn<Source<E>, Source<F>>
): Source<F>;

function pipe<T, A, B, C, D, E, F, G>(
  source: Source<T>,
  op1: UnaryFn<Source<T>, Source<A>>,
  op2: UnaryFn<Source<A>, Source<B>>,
  op3: UnaryFn<Source<B>, Source<C>>,
  op4: UnaryFn<Source<C>, Source<D>>,
  op5: UnaryFn<Source<D>, Source<E>>,
  op6: UnaryFn<Source<E>, Source<F>>,
  op7: UnaryFn<Source<F>, Source<G>>
): Source<G>;

function pipe<T, A, B, C, D, E, F, G, H>(
  source: Source<T>,
  op1: UnaryFn<Source<T>, Source<A>>,
  op2: UnaryFn<Source<A>, Source<B>>,
  op3: UnaryFn<Source<B>, Source<C>>,
  op4: UnaryFn<Source<C>, Source<D>>,
  op5: UnaryFn<Source<D>, Source<E>>,
  op6: UnaryFn<Source<E>, Source<F>>,
  op7: UnaryFn<Source<F>, Source<G>>,
  op8: UnaryFn<Source<G>, Source<H>>
): Source<H>;

/* pipe definitions for source + operators + consumer composition */

function pipe<T, R>(source: Source<T>, consumer: UnaryFn<Source<T>, R>): R;

function pipe<T, A, R>(
  source: Source<T>,
  op1: UnaryFn<Source<T>, Source<A>>,
  consumer: UnaryFn<Source<A>, R>
): R;

function pipe<T, A, B, R>(
  source: Source<T>,
  op1: UnaryFn<Source<T>, Source<A>>,
  op2: UnaryFn<Source<A>, Source<B>>,
  consumer: UnaryFn<Source<B>, R>
): R;

function pipe<T, A, B, C, R>(
  source: Source<T>,
  op1: UnaryFn<Source<T>, Source<A>>,
  op2: UnaryFn<Source<A>, Source<B>>,
  op3: UnaryFn<Source<B>, Source<C>>,
  consumer: UnaryFn<Source<C>, R>
): R;

function pipe<T, A, B, C, D, R>(
  source: Source<T>,
  op1: UnaryFn<Source<T>, Source<A>>,
  op2: UnaryFn<Source<A>, Source<B>>,
  op3: UnaryFn<Source<B>, Source<C>>,
  op4: UnaryFn<Source<C>, Source<D>>,
  consumer: UnaryFn<Source<D>, R>
): R;

function pipe<T, A, B, C, D, E, R>(
  source: Source<T>,
  op1: UnaryFn<Source<T>, Source<A>>,
  op2: UnaryFn<Source<A>, Source<B>>,
  op3: UnaryFn<Source<B>, Source<C>>,
  op4: UnaryFn<Source<C>, Source<D>>,
  op5: UnaryFn<Source<D>, Source<E>>,
  consumer: UnaryFn<Source<E>, R>
): R;

function pipe<T, A, B, C, D, E, F, R>(
  source: Source<T>,
  op1: UnaryFn<Source<T>, Source<A>>,
  op2: UnaryFn<Source<A>, Source<B>>,
  op3: UnaryFn<Source<B>, Source<C>>,
  op4: UnaryFn<Source<C>, Source<D>>,
  op5: UnaryFn<Source<D>, Source<E>>,
  op6: UnaryFn<Source<E>, Source<F>>,
  consumer: UnaryFn<Source<F>, R>
): R;

function pipe<T, A, B, C, D, E, F, G, R>(
  source: Source<T>,
  op1: UnaryFn<Source<T>, Source<A>>,
  op2: UnaryFn<Source<A>, Source<B>>,
  op3: UnaryFn<Source<B>, Source<C>>,
  op4: UnaryFn<Source<C>, Source<D>>,
  op5: UnaryFn<Source<D>, Source<E>>,
  op6: UnaryFn<Source<E>, Source<F>>,
  op7: UnaryFn<Source<F>, Source<G>>,
  consumer: UnaryFn<Source<G>, R>
): R;

function pipe<T, A, B, C, D, E, F, G, H, R>(
  source: Source<T>,
  op1: UnaryFn<Source<T>, Source<A>>,
  op2: UnaryFn<Source<A>, Source<B>>,
  op3: UnaryFn<Source<B>, Source<C>>,
  op4: UnaryFn<Source<C>, Source<D>>,
  op5: UnaryFn<Source<D>, Source<E>>,
  op6: UnaryFn<Source<E>, Source<F>>,
  op7: UnaryFn<Source<F>, Source<G>>,
  op8: UnaryFn<Source<G>, Source<H>>,
  consumer: UnaryFn<Source<H>, R>
): R;

function pipe() {
  let x = arguments[0];
  for (let i = 1, l = arguments.length; i < l; i++)
    x = arguments[i](x);
  return x;
}

export { pipe };
