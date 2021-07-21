import * as React from "react";
/**
 * React.Ref uses the readonly type `React.RefObject` instead of
 * `React.MutableRefObject`, We pretty much always assume ref objects are
 * mutable (at least when we create them), so this type is a workaround so some
 * of the weird mechanics of using refs with TS.
 */
export declare type AssignableRef<ValueType> = {
    bivarianceHack(instance: ValueType | null): void;
}["bivarianceHack"] | React.MutableRefObject<ValueType | null>;
/**
 * Type can be either a single `ValueType` or an array of `ValueType`
 */
export declare type SingleOrArray<ValueType> = ValueType[] | ValueType;
/**
 * The built-in utility type `Omit` does not distribute over unions. So if you
 * have:
 *
 *    type A = { a: 'whatever' }
 *
 * and you want to do a union with:
 *
 *    type B = A & { b: number } | { b: string; c: number }
 *
 * you might expect `Omit<B, 'a'>` to give you:
 *
 *    type B =
 *      | Omit<{ a: "whatever"; b: number }, "a">
        | Omit<{ a: "whatever"; b: string; c: number }, "a">;
 *
 * This is not the case, unfortunately, so we need to create our own version of
 * `Omit` that distributes over unions with a distributive conditional type. If
 * you have a generic type parameter `T`, then the construct
 * `T extends any ? F<T> : never` will end up distributing the `F<>` operation
 * over `T` when `T` is a union type.
 *
 * @link https://stackoverflow.com/a/59796484/1792019
 * @link http://www.typescriptlang.org/docs/handbook/advanced-types.html#distributive-conditional-types
 */
export declare type DistributiveOmit<BaseType, Key extends PropertyKey> = BaseType extends any ? Omit<BaseType, Key> : never;
/**
 * Returns the type inferred by a promise's return value.
 *
 * @example
 * async function getThing() {
 *   // return type is a number
 *   let result: number = await fetchValueSomewhere();
 *   return result;
 * }
 *
 * type Thing = ThenArg<ReturnType<typeof getThing>>;
 * // number
 */
export declare type ThenArg<T> = T extends PromiseLike<infer U> ? U : T;
export declare type As<BaseProps = any> = React.ElementType<BaseProps>;
export declare type PropsWithAs<ComponentType extends As, ComponentProps> = ComponentProps & Omit<React.ComponentPropsWithRef<ComponentType>, "as" | keyof ComponentProps> & {
    as?: ComponentType;
};
export declare type PropsFromAs<ComponentType extends As, ComponentProps> = (PropsWithAs<ComponentType, ComponentProps> & {
    as: ComponentType;
}) & PropsWithAs<ComponentType, ComponentProps>;
export declare type ComponentWithForwardedRef<ElementType extends React.ElementType, ComponentProps> = React.ForwardRefExoticComponent<ComponentProps & React.HTMLProps<React.ElementType<ElementType>> & React.ComponentPropsWithRef<ElementType>>;
export interface FunctionComponentWithAs<ComponentType extends As, ComponentProps> {
    /**
     * Inherited from React.FunctionComponent with modifications to support `as`
     */
    <TT extends As>(props: PropsWithAs<TT, ComponentProps>, context?: any): React.ReactElement<any, any> | null;
    (props: PropsWithAs<ComponentType, ComponentProps>, context?: any): React.ReactElement<any, any> | null;
    /**
     * Inherited from React.FunctionComponent
     */
    displayName?: string;
    propTypes?: React.WeakValidationMap<PropsWithAs<ComponentType, ComponentProps>>;
    contextTypes?: React.ValidationMap<any>;
    defaultProps?: Partial<PropsWithAs<ComponentType, ComponentProps>>;
}
export interface ComponentWithAs<ComponentType extends As, ComponentProps> extends FunctionComponentWithAs<ComponentType, ComponentProps> {
}
interface ExoticComponentWithAs<ComponentType extends As, ComponentProps> {
    /**
     * **NOTE**: Exotic components are not callable.
     * Inherited from React.ExoticComponent with modifications to support `as`
     */
    <TT extends As>(props: PropsWithAs<TT, ComponentProps>): React.ReactElement | null;
    (props: PropsWithAs<ComponentType, ComponentProps>): React.ReactElement | null;
    /**
     * Inherited from React.ExoticComponent
     */
    readonly $$typeof: symbol;
}
interface NamedExoticComponentWithAs<ComponentType extends As, ComponentProps> extends ExoticComponentWithAs<ComponentType, ComponentProps> {
    /**
     * Inherited from React.NamedExoticComponent
     */
    displayName?: string;
}
export interface ForwardRefExoticComponentWithAs<ComponentType extends As, ComponentProps> extends NamedExoticComponentWithAs<ComponentType, ComponentProps> {
    /**
     * Inherited from React.ForwardRefExoticComponent
     * Will show `ForwardRef(${Component.displayName || Component.name})` in devtools by default,
     * but can be given its own specific name
     */
    defaultProps?: Partial<PropsWithAs<ComponentType, ComponentProps>>;
    propTypes?: React.WeakValidationMap<PropsWithAs<ComponentType, ComponentProps>>;
}
export interface MemoExoticComponentWithAs<ComponentType extends As, ComponentProps> extends NamedExoticComponentWithAs<ComponentType, ComponentProps> {
    readonly type: ComponentType extends React.ComponentType ? ComponentType : FunctionComponentWithAs<ComponentType, ComponentProps>;
}
export interface ForwardRefWithAsRenderFunction<ComponentType extends As, ComponentProps = {}> {
    (props: React.PropsWithChildren<PropsFromAs<ComponentType, ComponentProps>>, ref: ((instance: (ComponentType extends keyof ElementTagNameMap ? ElementByTag<ComponentType> : any) | null) => void) | React.MutableRefObject<(ComponentType extends keyof ElementTagNameMap ? ElementByTag<ComponentType> : any) | null> | null): React.ReactElement | null;
    displayName?: string;
    /**
     * defaultProps are not supported on render functions
     */
    defaultProps?: never;
    /**
     * propTypes are not supported on render functions
     */
    propTypes?: never;
}
export declare type ElementTagNameMap = HTMLElementTagNameMap & Pick<SVGElementTagNameMap, Exclude<keyof SVGElementTagNameMap, keyof HTMLElementTagNameMap>>;
export declare type ElementByTag<TagName extends keyof ElementTagNameMap> = ElementTagNameMap[TagName];
export {};
