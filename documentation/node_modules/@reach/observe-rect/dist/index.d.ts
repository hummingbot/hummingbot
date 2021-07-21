export default function observeRect(node: Element, cb: (rect: DOMRect) => void): {
    observe(): void;
    unobserve(): void;
};
export declare type PartialRect = Partial<DOMRect>;
export declare type RectProps = {
    rect: DOMRect | undefined;
    hasRectChanged: boolean;
    callbacks: Function[];
};
