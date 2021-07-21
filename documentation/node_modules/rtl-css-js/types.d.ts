declare interface RtlCSSJS {
  default: RtlCSSJS
  <T extends object = object>(o: T): T
}

declare const rtlCSSJS: RtlCSSJS

export = rtlCSSJS
