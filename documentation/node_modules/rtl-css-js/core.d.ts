export declare type PropertyValue = string | number | object

export declare interface CommonConverterOptions {
  value: string
}

export declare interface BackgroundConverterOptions {
  value: string
  valuesToConvert: {[source: string]: string}
  isRtl: boolean
  bgImgDirectionRegex: RegExp
  bgPosDirectionRegex: RegExp
}

export declare interface BackgroundImageConverterOptions {
  value: string
  valuesToConvert: {[source: string]: string}
  bgImgDirectionRegex: RegExp
}

export declare interface BackgroundPositionConverterOptions {
  value: string
  valuesToConvert: {[source: string]: string}
  isRtl: boolean
  bgPosDirectionRegex: RegExp
}

export declare interface PropertyValueConverter<
  O extends CommonConverterOptions = CommonConverterOptions
> {
  (options: O): string
}

export declare interface PropertyValueConverters {
  padding: PropertyValueConverter
  textShadow: PropertyValueConverter
  borderColor: PropertyValueConverter
  borderRadius: PropertyValueConverter
  background: PropertyValueConverter<BackgroundConverterOptions>
  backgroundImage: PropertyValueConverter<BackgroundImageConverterOptions>
  backgroundPosition: PropertyValueConverter<BackgroundPositionConverterOptions>
  backgroundPositionX: PropertyValueConverter<
    BackgroundPositionConverterOptions
  >
  objectPosition: PropertyValueConverter<BackgroundPositionConverterOptions>
  transform: PropertyValueConverter
  margin: PropertyValueConverter
  borderWidth: PropertyValueConverter
  boxShadow: PropertyValueConverter
  webkitBoxShadow: PropertyValueConverter
  mozBoxShadow: PropertyValueConverter
  borderStyle: PropertyValueConverter
  webkitTransform: PropertyValueConverter
  mozTransform: PropertyValueConverter
  'text-shadow': PropertyValueConverter
  'border-color': PropertyValueConverter
  'border-radius': PropertyValueConverter
  'background-image': PropertyValueConverter<BackgroundImageConverterOptions>
  'background-position': PropertyValueConverter<
    BackgroundPositionConverterOptions
  >
  'background-position-x': PropertyValueConverter<
    BackgroundPositionConverterOptions
  >
  'object-position': PropertyValueConverter<
    BackgroundPositionConverterOptions
  >
  'border-width': PropertyValueConverter
  'box-shadow': PropertyValueConverter
  '-webkit-box-shadow': PropertyValueConverter
  '-moz-box-shadow': PropertyValueConverter
  'border-style': PropertyValueConverter
  '-webkit-transform': PropertyValueConverter
  '-moz-transform': PropertyValueConverter
}

export declare const propertyValueConverters: PropertyValueConverters

/**
 * Takes an array of [keyValue1, keyValue2] pairs and creates an object of {keyValue1: keyValue2, keyValue2: keyValue1}
 * @param {Array} array the array of pairs
 * @return {Object} the {key, value} pair object
 */
export declare function arrayToObject(
  array: string[][],
): {[source: string]: string}

/**
 * Flip the sign of a CSS value, possibly with a unit.
 *
 * We can't just negate the value with unary minus due to the units.
 *
 * @private
 * @param {String} value - the original value (for example 77%)
 * @return {String} the result (for example -77%)
 */
export declare function flipSign(value: string): string

/**
 * Takes a percentage for background position and inverts it.
 * This was copied and modified from CSSJanus:
 * https://github.com/cssjanus/cssjanus/blob/4245f834365f6cfb0239191a151432fb85abab23/src/cssjanus.js#L152-L175
 * @param {String} value - the original value (for example 77%)
 * @return {String} the result (for example 23%)
 */
export declare function calculateNewBackgroundPosition(value: string): string

/**
 * This takes a list of CSS values and converts it to an array
 * @param {String} value - something like `1px`, `1px 2em`, or `3pt rgb(150, 230, 550) 40px calc(100% - 5px)`
 * @return {Array} the split values (for example: `['3pt', 'rgb(150, 230, 550)', '40px', 'calc(100% - 5px)']`)
 */
export declare function getValuesAsList(value: string): string[]

/**
 * This is intended for properties that are `top right bottom left` and will switch them to `top left bottom right`
 * @param {String} value - `1px 2px 3px 4px` for example, but also handles cases where there are too few/too many and
 * simply returns the value in those cases (which is the correct behavior)
 * @return {String} the result - `1px 4px 3px 2px` for example.
 */
export declare function handleQuartetValues(value: string): string

export declare const propertiesToConvert: {[key: string]: string}

export declare const valuesToConvert: {[key: string]: string}

export declare const propsToIgnore: string[]

/**
 * converts properties and values in the CSS in JS object to their corresponding RTL values
 * @param {Object} object the CSS in JS object
 * @return {Object} the RTL converted object
 */
export declare function convert<T extends object = object>(o: T): T

/**
 * Converts a property and its value to the corresponding RTL key and value
 * @param {String} originalKey the original property key
 * @param {Number|String|Object} originalValue the original css property value
 * @return {Object} the new {key, value} pair
 */
export declare function convertProperty<V extends PropertyValue>(
  originalKey: string,
  originalValue: V,
): {key: string; value: V}

/**
 * This gets the RTL version of the given property if it has a corresponding RTL property
 * @param {String} property the name of the property
 * @return {String} the name of the RTL property
 */
export declare function getPropertyDoppelganger(property: string): string

/**
 * This converts the given value to the RTL version of that value based on the key
 * @param {String} key this is the key (note: this should be the RTL version of the originalKey)
 * @param {String|Number|Object} originalValue the original css property value. If it's an object, then we'll convert that as well
 * @return {String|Number|Object} the converted value
 */
export declare function getValueDoppelganger<V extends PropertyValue>(
  key: string,
  originalValue: V,
): V
