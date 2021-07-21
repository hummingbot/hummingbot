import { RefObject } from 'react';
export interface State {
    docX: number;
    docY: number;
    posX: number;
    posY: number;
    elX: number;
    elY: number;
    elH: number;
    elW: number;
}
declare const useMouse: (ref: RefObject<HTMLElement>) => State;
export default useMouse;
