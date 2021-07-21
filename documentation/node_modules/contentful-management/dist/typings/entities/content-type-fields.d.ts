export interface NumRange {
    min?: number;
    max?: number;
}
export interface DateRange {
    min?: string;
    max?: string;
}
export interface RegExp {
    pattern: string;
    flags: string;
}
export interface Validation {
    linkContentType?: string[];
    in?: string[];
    linkMimetypeGroup?: string[];
    enabledNodeTypes?: string[];
    enabledMarks?: string[];
    unique?: boolean;
    size?: NumRange;
    range?: NumRange;
    dateRange?: DateRange;
    regexp?: RegExp;
    prohibitRegexp?: RegExp;
    assetImageDimensions?: {
        width?: NumRange;
        height?: NumRange;
    };
    assetFileSize?: NumRange;
}
export interface Item {
    type: string;
    linkType?: string;
    validations?: Validation[];
}
export interface ContentFields extends Item {
    id: string;
    name: string;
    required: boolean;
    localized: boolean;
    disabled?: boolean;
    omitted?: boolean;
    items?: Item;
}
