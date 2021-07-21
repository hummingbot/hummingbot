import { RefObject } from 'react';
export interface FullScreenOptions {
    video?: RefObject<HTMLVideoElement>;
    onClose?: (error?: Error) => void;
}
declare const useFullscreen: (ref: RefObject<Element>, on: boolean, options?: FullScreenOptions) => boolean;
export default useFullscreen;
