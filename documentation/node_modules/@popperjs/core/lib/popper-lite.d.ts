import { popperGenerator, detectOverflow } from "./createPopper";
export * from "./types";
declare const defaultModifiers: (import("./types").Modifier<"popperOffsets", {}> | import("./types").Modifier<"eventListeners", import("./modifiers/eventListeners").Options> | import("./types").Modifier<"computeStyles", import("./modifiers/computeStyles").Options> | import("./types").Modifier<"applyStyles", {}>)[];
declare const createPopper: <TModifier extends Partial<import("./types").Modifier<any, any>>>(reference: Element | import("./types").VirtualElement, popper: HTMLElement, options?: Partial<import("./types").OptionsGeneric<TModifier>>) => import("./types").Instance;
export { createPopper, popperGenerator, defaultModifiers, detectOverflow };
