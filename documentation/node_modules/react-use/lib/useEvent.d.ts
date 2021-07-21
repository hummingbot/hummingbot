export interface ListenerType1 {
    addEventListener(name: string, handler: (event?: any) => void, ...args: any[]): any;
    removeEventListener(name: string, handler: (event?: any) => void): any;
}
export interface ListenerType2 {
    on(name: string, handler: (event?: any) => void, ...args: any[]): any;
    off(name: string, handler: (event?: any) => void): any;
}
export declare type UseEventTarget = ListenerType1 | ListenerType2;
declare const useEvent: (name: string, handler?: ((event?: any) => void) | null | undefined, target?: ListenerType1 | ListenerType2 | null, options?: any) => void;
export default useEvent;
