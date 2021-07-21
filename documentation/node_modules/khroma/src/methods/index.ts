
/* IMPORT */

import hex from './rgba'; // Alias
import rgb from './rgba'; // Alias
import rgba from './rgba';
import hsl from './hsla'; // Alias
import hsla from './hsla';
import channel from './channel';
import red from './red';
import green from './green';
import blue from './blue';
import hue from './hue';
import saturation from './saturation';
import lightness from './lightness';
import alpha from './alpha';
import opacity from './alpha'; // Alias
import luminance from './luminance';
import isDark from './is_dark';
import isLight from './is_light';
import isValid from './is_valid';
import saturate from './saturate';
import desaturate from './desaturate';
import lighten from './lighten';
import darken from './darken';
import opacify from './opacify';
import fadeIn from './opacify'; // Alias
import transparentize from './transparentize';
import fadeOut from './transparentize'; // Alias
import complement from './complement';
import grayscale from './grayscale';
import adjust from './adjust';
import change from './change';
import invert from './invert';
import mix from './mix';
import scale from './scale';

/* EXPORT */

export {
  /* CREATE */
  hex,
  rgb,
  rgba,
  hsl,
  hsla,
  /* GET - CHANNEL */
  channel,
  red,
  green,
  blue,
  hue,
  saturation,
  lightness,
  alpha,
  opacity,
  /* GET - MORE */
  luminance,
  isDark,
  isLight,
  isValid,
  /* EDIT - CHANNEL */
  saturate,
  desaturate,
  lighten,
  darken,
  opacify,
  fadeIn,
  transparentize,
  fadeOut,
  complement,
  grayscale,
  /* EDIT - MORE */
  adjust,
  change,
  invert,
  mix,
  scale
};
