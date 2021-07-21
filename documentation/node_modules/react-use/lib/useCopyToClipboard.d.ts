export interface CopyToClipboardState {
    value?: string;
    noUserInteraction: boolean;
    error?: Error;
}
declare const useCopyToClipboard: () => [CopyToClipboardState, (value: string) => void];
export default useCopyToClipboard;
