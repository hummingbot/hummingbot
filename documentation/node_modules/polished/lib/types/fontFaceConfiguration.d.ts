declare interface FontFaceConfiguration {
  fontFamily: string;
  fontFilePath?: string;
  fontStretch?: string;
  fontStyle?: string;
  fontVariant?: string;
  fontWeight?: string;
  fileFormats?: Array<string>;
  localFonts?: Array<string>;
  unicodeRange?: string;
  fontDisplay?: string;
  fontVariationSettings?: string;
  fontFeatureSettings?: string;
}

export { FontFaceConfiguration };
