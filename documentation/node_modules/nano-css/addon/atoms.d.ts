import * as CSS from 'csstype';
import {NanoRenderer} from '../types/nano';

type TLength = string | number;

export interface Atoms {
    /**
     * Short for `display` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    d?: CSS.DisplayProperty;

    /**
     * Short for `margin` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    mar?: CSS.MarginProperty<TLength>;

    /**
     * Short for `margin-top` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    mart?: CSS.MarginBottomProperty<TLength>;

    /**
     * Short for `margin-right` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    marr?: CSS.MarginBottomProperty<TLength>;

    /**
     * Short for `margin-bottom` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    marb?: CSS.MarginBottomProperty<TLength>;

    /**
     * Short for `margin-left` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    marl?: CSS.MarginBottomProperty<TLength>;

    /**
     * Short for `padding` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    pad?: CSS.PaddingProperty<TLength>;

    /**
     * Short for `padding-top` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    padt?: CSS.PaddingBottomProperty<TLength>;

    /**
     * Short for `padding-right` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    padr?: CSS.PaddingBottomProperty<TLength>;

    /**
     * Short for `padding-bottom` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    padb?: CSS.PaddingBottomProperty<TLength>;

    /**
     * Short for `padding-left` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    padl?: CSS.PaddingBottomProperty<TLength>;

    /**
     * Short for `border` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    bd?: CSS.BorderBottomProperty<TLength>;

    /**
     * Short for `border-top` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    bdt?: CSS.BorderBottomProperty<TLength>;

    /**
     * Short for `border-right` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    bdr?: CSS.BorderBottomProperty<TLength>;

    /**
     * Short for `border-bottom` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    bdb?: CSS.BorderBottomProperty<TLength>;

    /**
     * Short for `border-left` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    bdl?: CSS.BorderBottomProperty<TLength>;

    /**
     * Short for `border-radius` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    bdrad?: CSS.BorderRadiusProperty<TLength>;

    /**
     * Short for `color` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    col?: CSS.Color;

    /**
     * Short for `opacity` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    op?: number | string;

    /**
     * Short for `background` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    bg?: CSS.BackgroundProperty<TLength>;

    /**
     * Short for `background-color` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    bgc?: CSS.BackgroundColorProperty;

    /**
     * Short for `font-size` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    fz?: CSS.FontSizeProperty<TLength>;

    /**
     * Short for `font-style` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    fs?: CSS.FontStyleProperty;

    /**
     * Short for `font-weight` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    fw?: CSS.FontWeightProperty;

    /**
     * Short for `font-family` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    ff?: CSS.FontFamilyProperty;

    /**
     * Short for `line-height` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    lh?: CSS.LineHeightProperty<TLength>;

    /**
     * Short for `box-sizing` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    bxz?: CSS.BoxSizingProperty;

    /**
     * Short for `cursor` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    cur?: CSS.CursorProperty;

    /**
     * Short for `overflow` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    ov?: CSS.OverflowProperty;

    /**
     * Short for `position` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    pos?: CSS.PositionProperty;

    /**
     * Short for `list-style` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    ls?: CSS.ListStyleProperty;

    /**
     * Short for `text-align` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    ta?: CSS.TextAlignProperty;

    /**
     * Short for `text-decoration` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    td?: CSS.TextDecorationProperty<TLength>;

    /**
     * Short for `float` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    fl?: CSS.FloatProperty;

    /**
     * Short for `width` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    w?: CSS.WidthProperty<TLength>;

    /**
     * Short for `min-width` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    minW?: CSS.MinWidthProperty<TLength>;

    /**
     * Short for `max-width` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    maxW?: CSS.MaxWidthProperty<TLength>;

    /**
     * Short for `min-height` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    minH?: CSS.MinHeightProperty<TLength>;

    /**
     * Short for `max-height` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    maxH?: CSS.MaxHeightProperty<TLength>;

    /**
     * Short for `height` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    h?: CSS.HeightProperty<TLength>;

    /**
     * Short for `transition` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    trs?: CSS.TransitionProperty;

    /**
     * Short for `outline` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    out?: CSS.OutlineProperty<TLength>;

    /**
     * Short for `visibility` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    vis?: CSS.VisibilityProperty;

    /**
     * Short for `word-wrap` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    ww?: CSS.WordWrapProperty;

    /**
     * Short for `content` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    con?: CSS.ContentProperty;

    /**
     * Short for `z-index` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    z?: CSS.ZIndexProperty;

    /**
     * Short for `transform` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    tr?: CSS.TransformProperty;
}

export function addon(nano: NanoRenderer);
