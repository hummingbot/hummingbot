import { Handler, KeyFilter } from './useKey';
declare const useKeyPressEvent: (key: KeyFilter, keydown?: Handler | null | undefined, keyup?: Handler | null | undefined, useKeyPress?: (keyFilter: KeyFilter) => [boolean, KeyboardEvent | null]) => void;
export default useKeyPressEvent;
