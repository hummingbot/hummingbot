import * as polished from "./lib/index";
import { ENGINE_METHOD_NONE } from "constants";

/*
 * Mixins
 */
let between: string = polished.between("20px", "100px", "400px", "1000px");
between = polished.between("20px", "100px");

let clearFix: object = polished.clearFix();
clearFix = polished.clearFix("&");

let cover: object = polished.cover();
cover = polished.cover("100px");

let ellipsis: object = polished.ellipsis();
ellipsis = polished.ellipsis("250px");

let fluidRange: object = polished.fluidRange(
  {
    prop: 'padding',
    fromSize: '20px',
    toSize: '100px',
  },
  '400px',
  '1000px',
);

fluidRange = polished.fluidRange(
  [
    {
      prop: 'padding',
      fromSize: '20px',
      toSize: '100px',
    },
    {
      prop: 'margin',
      fromSize: '5px',
      toSize: '25px',
    },
  ],
  '400px',
  '1000px',
);

fluidRange = polished.fluidRange({
  prop: 'padding',
  fromSize: '20px',
  toSize: '100px',
});

const fontFace: object = polished.fontFace({
  fontFamily: "Sans-Pro",
  fontFilePath: "path/to/file",
  fontStretch: "",
  fontStyle: "",
  fontVariant: "",
  fontWeight: "",
  fileFormats: [""],
  localFonts: [""],
  unicodeRange: ""
});

const hideText: object = polished.hideText();
const hideVisually: object = polished.hideVisually();

let hiDPI: string = polished.hiDPI();
hiDPI = polished.hiDPI(1.5);

const normalize: object = polished.normalize();

let placeholder: object = polished.placeholder({});
placeholder = polished.placeholder({}, "");

const radialGradient: object = polished.radialGradient({
  colorStops: ["#00FFFF 0%", "rgba(0, 0, 255, 0) 50%", "#0000FF 95%"],
  extent: "farthest-corner at 45px 45px",
  position: "center",
  shape: "ellipse",
  fallback: ""
});

let retinaImage: object = polished.retinaImage("");
retinaImage = polished.retinaImage("", "");
retinaImage = polished.retinaImage("", "", "");
retinaImage = polished.retinaImage("", "", "", "");
retinaImage = polished.retinaImage("", "", "", "", "");

let selection: object = polished.selection({});
selection = polished.selection({}, "");

const timingFunctions = polished.timingFunctions("easeInBack");

const triangle = polished.triangle({
  backgroundColor: "red",
  foregroundColor: "red",
  pointingDirection: "right",
  width: 100,
  height: 100,
});

let wordWrap: object = polished.wordWrap();
wordWrap = polished.wordWrap("");

/*
 * Colors
 */
const adjustHue: string = polished.adjustHue(180, "#448");
const complement: string = polished.complement("#448");
const darken: string = polished.darken(0.2, "#FFCD64");
const desaturate: string = polished.desaturate(0.2, "#CCCD64");
const getLuminance: number = polished.getLuminance('#6564CDB3');
const grayscale: string = polished.grayscale("#CCCD64");

let hsl: string = polished.hsl(359, 0.75, 0.4);
hsl = polished.hsl({ hue: 360, saturation: 0.75, lightness: 0.4 });

let hsla: string = polished.hsla(359, 0.75, 0.4, 0.7);
hsla = polished.hsla({ hue: 360, saturation: 0.75, lightness: 0.4, alpha: 0.7 });

const invert: string = polished.invert("#CCCD64");
const lighten: string = polished.lighten(0.2, "#CCCD64");
const mix: string = polished.mix(0.5, "#f00", "#00f");
const opacify: string = polished.opacify(0.1, "rgba(255, 255, 255, 0.9)");
const parseToHsl = polished.parseToHsl("rgb(255, 0, 0)");
const parseToRgb = polished.parseToRgb("rgb(255, 0, 0)");
const readableColor = polished.readableColor("rgb(255,0,0)");

let rgb: string = polished.rgb(255, 205, 100);
rgb = polished.rgb({ red: 255, green: 205, blue: 100 });

let rgba: string = polished.rgba(255, 205, 100, 0.7);
rgba = polished.rgba({ red: 255, green: 205, blue: 100, alpha: 0.7 });

const saturate: string = polished.saturate(0.2, "#CCCD64");
const setHue: string = polished.setHue(42, "#CCCD64");
const setLightness: string = polished.setLightness(0.2, "#CCCD64");
const setSaturation: string = polished.setSaturation(0.2, "#CCCD64");
const shade: string = polished.shade(0.25, "#00f");
const tint: string = polished.tint(0.25, "#00f");

let toColorString: string = polished.toColorString({ red: 255, green: 205, blue: 100 });
toColorString = polished.toColorString({ red: 255, green: 205, blue: 100, alpha: 0.72 });
toColorString = polished.toColorString({ hue: 240, saturation: 1, lightness: 0.5 });
toColorString = polished.toColorString({ hue: 360, saturation: 0.75, lightness: 0.4, alpha: 0.72 });

const transparentize: string = polished.transparentize(0.1, "#fff");

/*
 * Shorthands
 */
const animation: object = polished.animation(["rotate", 1, "ease-in-out"], ["colorchange", "2s"]);
const backgroundImages: object = polished.backgroundImages('url("/image/background.jpg")', 'linear-gradient(red, green)');
const backgrounds: object = polished.backgrounds('url("/image/background.jpg")', "linear-gradient(red, green)", "center no-repeat");
const border: object = polished.border('top', '1px', 'solid', 'red');
const borderColor: object = polished.borderColor("red", null, undefined, "green");
const borderRadius: object = polished.borderRadius("top", "5px");
const borderStyle: object = polished.borderStyle("solid", null, undefined, "dashed");
const borderWidth: object = polished.borderWidth("12px", null, undefined, "24px");
const buttons: string = polished.buttons(null, undefined, "active");
const margin: object = polished.margin("12px", null, undefined, "24px");
const padding: object = polished.padding("12px", null, undefined, "24px");

let position: object = polished.position(null);
polished.position("absolute", "12px", null, undefined, "24px");
position = polished.position(null, "12px", null, undefined, "24px");
position = polished.position(undefined, "12px", null, undefined, "24px");

let size: object = polished.size("");
size = polished.size("", "");

const textInputs: string = polished.textInputs("active", null, undefined);
const transitions: object = polished.transitions("opacity 1.0s ease-in 0s", "width 2.0s ease-in 2s");

/*
 * Helpers
 */
const directionalProperty: object = polished.directionalProperty("padding", "12px", null, undefined, "24px");

let em: string = polished.em("12px");
em = polished.em(12);

const getValueAndUnit: [number | string, string | void] = polished.getValueAndUnit('100px');

let modularScale: string = polished.modularScale(2);
modularScale = polished.modularScale(2, 2);
modularScale = polished.modularScale(2, "");
modularScale = polished.modularScale(2, 2, 5);
modularScale = polished.modularScale(2, 2, "minorSecond");

let rem: string = polished.rem("12px");
rem = polished.rem(12);

const stripUnit: number | string = polished.stripUnit("100px");
