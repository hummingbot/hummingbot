export interface Symbol {
    type: 'Symbol';
}
export interface Text {
    type: 'Text';
}
export interface RichText {
    type: 'RichText';
}
export interface Integer {
    type: 'Integer';
}
export interface Number {
    type: 'Number';
}
export interface Date {
    type: 'Date';
}
export interface Boolean {
    type: 'Boolean';
}
export interface Object {
    type: 'Object';
}
export interface Location {
    type: 'Location';
}
export interface Asset {
    type: 'Link';
    linkType: 'Asset';
}
export interface Entry {
    type: 'Link';
    linkType: 'Entry';
}
export interface Array {
    type: 'Array';
    items: Entry | Asset | symbol;
}
export declare type EntryFields = symbol | Text | RichText | Integer | number | Date | boolean | Record<string, any> | Location | Entry | Array;
