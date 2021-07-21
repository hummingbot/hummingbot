// tslint:disable-next-line:max-classes-per-file
export abstract class EmptyList {
  protected opaque: any;
}

// tslint:disable-next-line:max-classes-per-file
export abstract class Cons<T> {
  protected opaque!: T;
}

export type list<T> = Cons<T> | EmptyList;
