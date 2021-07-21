import * as React from 'react';
export interface DropAreaState {
    over: boolean;
}
export interface DropAreaBond {
    onDragOver: React.DragEventHandler;
    onDragEnter: React.DragEventHandler;
    onDragLeave: React.DragEventHandler;
    onDrop: React.DragEventHandler;
    onPaste: React.ClipboardEventHandler;
}
export interface DropAreaOptions {
    onFiles?: (files: File[], event?: any) => void;
    onText?: (text: string, event?: any) => void;
    onUri?: (url: string, event?: any) => void;
}
declare const useDrop: (options?: DropAreaOptions, args?: never[]) => DropAreaState;
export default useDrop;
