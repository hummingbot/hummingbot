export declare abstract class EmptyList {
    protected opaque: any;
}
export declare abstract class Cons<T> {
    protected opaque: T;
}
export declare type list<T> = Cons<T> | EmptyList;
