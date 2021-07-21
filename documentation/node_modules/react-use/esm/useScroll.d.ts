import { RefObject } from 'react';
export interface State {
    x: number;
    y: number;
}
declare const useScroll: (ref: RefObject<HTMLElement>) => State;
export default useScroll;
