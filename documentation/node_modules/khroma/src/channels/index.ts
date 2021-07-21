
/* IMPORT */

import _ from '../utils';
import {TYPE, RGBA, HSLA, CHANNELS} from '../types';
import Type from './type';

/* CHANNELS */

class Channels {

  /* VARIABLES */

  color?: string;
  changed: boolean;
  data: CHANNELS; //TSC: It should really be "Partial<CHANNELS>", but TS gets excessively noisy
  type: Type;

  /* CONSTRUCTOR */

  constructor ( data: RGBA | HSLA | CHANNELS, color?: string ) {

    this.color = color;
    this.changed = false;
    this.data = data as CHANNELS; //TSC
    this.type = new Type ();

  }

  /* API */

  set ( data: RGBA | HSLA | CHANNELS, color?: string ): this {

    this.color = color;
    this.changed = false;
    this.data = data as CHANNELS; //TSC
    this.type.type = TYPE.ALL;

    return this;

  }

  /* HELPERS */

  _ensureHSL () {

    if (this.data.h === undefined ) this.data.h = _.channel.rgb2hsl ( this.data, 'h' );
    if (this.data.s === undefined ) this.data.s = _.channel.rgb2hsl ( this.data, 's' );
    if (this.data.l === undefined ) this.data.l = _.channel.rgb2hsl ( this.data, 'l' );

  }

  _ensureRGB () {

    if (this.data.r === undefined ) this.data.r = _.channel.hsl2rgb ( this.data, 'r' );
    if (this.data.g === undefined ) this.data.g = _.channel.hsl2rgb ( this.data, 'g' );
    if (this.data.b === undefined ) this.data.b = _.channel.hsl2rgb ( this.data, 'b' );

  }

  /* GETTERS */

  get r (): number {
    if ( !this.type.is ( TYPE.HSL ) && this.data.r !== undefined ) return this.data.r;
    this._ensureHSL ();
    return _.channel.hsl2rgb ( this.data, 'r' );
  }

  get g (): number {
    if ( !this.type.is ( TYPE.HSL ) && this.data.g !== undefined ) return this.data.g;
    this._ensureHSL ();
    return _.channel.hsl2rgb ( this.data, 'g' );
  }

  get b (): number {
    if ( !this.type.is ( TYPE.HSL ) && this.data.b !== undefined ) return this.data.b;
    this._ensureHSL ();
    return _.channel.hsl2rgb ( this.data, 'b' );
  }

  get h (): number {
    if ( !this.type.is ( TYPE.RGB ) && this.data.h !== undefined ) return this.data.h;
    this._ensureRGB ();
    return _.channel.rgb2hsl ( this.data, 'h' );
  }

  get s (): number {
    if ( !this.type.is ( TYPE.RGB ) && this.data.s !== undefined ) return this.data.s;
    this._ensureRGB ();
    return _.channel.rgb2hsl ( this.data, 's' );
  }

  get l (): number {
    if ( !this.type.is ( TYPE.RGB ) && this.data.l !== undefined ) return this.data.l;
    this._ensureRGB ();
    return _.channel.rgb2hsl ( this.data, 'l' );
  }

  get a (): number {
    return this.data.a;
  }

  /* SETTERS */

  set r ( r: number ) {
    this.type.set ( TYPE.RGB );
    this.changed = true;
    this.data.r = r;
  }

  set g ( g: number ) {
    this.type.set ( TYPE.RGB );
    this.changed = true;
    this.data.g = g;
  }

  set b ( b: number ) {
    this.type.set ( TYPE.RGB );
    this.changed = true;
    this.data.b = b;
  }

  set h ( h: number ) {
    this.type.set ( TYPE.HSL );
    this.changed = true;
    this.data.h = h;
  }

  set s ( s: number ) {
    this.type.set ( TYPE.HSL );
    this.changed = true;
    this.data.s = s;
  }

  set l ( l: number ) {
    this.type.set ( TYPE.HSL );
    this.changed = true;
    this.data.l = l;
  }

  set a ( a: number ) {
    this.changed = true;
    this.data.a = a;
  }

}

/* EXPORT */

export default Channels;
