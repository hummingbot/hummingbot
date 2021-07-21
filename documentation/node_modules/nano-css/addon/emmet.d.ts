import * as CSS from 'csstype';
import {NanoRenderer} from '../types/nano';

type TLength = string | number;

export interface EmmetAddon {
    // Visual Formatting; //
    /**
     * Short for `position` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    pos?: CSS.PositionProperty;
    /**
     * Short for `top` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    t?: CSS.TopProperty<TLength>;
    /**
     * Short for `right` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    r?: CSS.RightProperty<TLength>;
    /**
     * Short for `bottom` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    b?: CSS.BottomProperty<TLength>;
    /**
     * Short for `left` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    l?: CSS.LeftProperty<TLength>;
    /**
     * Short for `z-index` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    z?: CSS.ZIndexProperty;
    /**
     * Short for `float` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    fl?: CSS.FloatProperty;
    /**
     * Short for `clear` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    cl?: CSS.ClearProperty;
    /**
     * Short for `display` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    d?: CSS.DisplayProperty;
    /**
     * Short for `visibility` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    v?: CSS.VisibilityProperty;
    /**
     * Short for `overflow` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    ov?: CSS.OverflowProperty;
    /**
     * Short for `overflow-x` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    ovx?: CSS.OverflowXProperty;
    /**
     * Short for `overflow-y` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    ovy?: CSS.OverflowYProperty;
    /**
     * Short for `overflow-style` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    ovs?: CSS.MsOverflowStyleProperty;
    /**
     * Short for `zoom` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    zm?: CSS.ZoomProperty;
    /**
     * Short for `clip` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    cp?: CSS.ClipProperty;
    /**
     * Short for `resize` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    rsz?: CSS.ResizeProperty;
    /**
     * Short for `cursor` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    cur?: CSS.CursorProperty;
    // Margin & Padding; //
    /**
     * Short for `margin` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    m?: CSS.MarginProperty<TLength>;
    /**
     * Short for `margin-top` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    mt?: CSS.MarginTopProperty<TLength>;
    /**
     * Short for `margin-right` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    mr?: CSS.MarginRightProperty<TLength>;
    /**
     * Short for `margin-bottom` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    mb?: CSS.MarginBottomProperty<TLength>;
    /**
     * Short for `margin-left` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    ml?: CSS.MarginLeftProperty<TLength>;
    /**
     * Short for `padding` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    p?: CSS.PaddingProperty<TLength>;
    /**
     * Short for `paddin-top` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    pt?: CSS.PaddingTopProperty<TLength>;
    /**
     * Short for `padding-right` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    pr?: CSS.PaddingRightProperty<TLength>;
    /**
     * Short for `padding-bottom` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    pb?: CSS.PaddingBottomProperty<TLength>;
    /**
     * Short for `padding-left` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    pl?: CSS.PaddingLeftProperty<TLength>;
    // Box Sizing; //
    /**
     * Short for `box-sizing` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    bxz?: CSS.BoxSizingProperty;
    /**
     * Short for `box-shadow` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    bxsh?: CSS.BoxShadowProperty;
    /**
     * Short for `width` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    w?: CSS.WidthProperty<TLength>;
    /**
     * Short for `height` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    h?: CSS.HeightProperty<TLength>;
    /**
     * Short for `max-width` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    maw?: CSS.MaxWidthProperty<TLength>;
    /**
     * Short for `max-height` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    mah?: CSS.MaxHeightProperty<TLength>;
    /**
     * Short for `min-width` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    miw?: CSS.MinWidthProperty<TLength>;
    /**
     * Short for `min-height` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    mih?: CSS.MinHeightProperty<TLength>;
    // Font; //
    /**
     * Short for `font` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    f?: CSS.FontProperty;
    /**
     * Short for `font-weight` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    fw?: CSS.FontWeightProperty;
    /**
     * Short for `font-style` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    fs?: CSS.FontStyleProperty;
    /**
     * Short for `font-variant` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    fv?: CSS.FontVariantProperty;
    /**
     * Short for `font-size` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    fz?: CSS.FontSizeProperty<TLength>;
    /**
     * Short for `font-family` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    ff?: CSS.FontFamilyProperty;
    /**
     * Short for `font-stretch` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    fst?: CSS.FontStretchProperty;

    // Text; //
    /**
     * Short for `vertical-align` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    va?: CSS.VerticalAlignProperty<TLength>;
    /**
     * Short for `text-align` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    ta?: CSS.TextAlignProperty;
    /**
     * Short for `text-decoration` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    td?: CSS.TextDecorationProperty<TLength>;
    /**
     * Short for `text-emphasis` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    te?: CSS.TextEmphasisProperty;
    /**
     * Short for `text-indent` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    ti?: CSS.TextIndentProperty<TLength>;
    /**
     * Short for `text-justify` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    tj?: CSS.TextJustifyProperty;
    /**
     * Short for `text-transform` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    tt?: CSS.TextTransformProperty;
    /**
     * Short for `text-shadow` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    tsh?: CSS.TextShadowProperty;
    /**
     * Short for `line-height` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    lh?: CSS.LineHeightProperty<TLength>;
    /**
     * Short for `letter-spacing` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    lts?: CSS.LetterSpacingProperty<TLength>;
    /**
     * Short for `white-space` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    whs?: CSS.WhiteSpaceProperty;
    /**
     * Short for `word-break` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    wob?: CSS.WordBreakProperty;
    /**
     * Short for `word-spacing` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    wos?: CSS.WordSpacingProperty<TLength>;
    /**
     * Short for `word-wrap` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    wow?: CSS.WordWrapProperty;
    // Background; //
    /**
     * Short for `background` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    bg?: CSS.BackgroundProperty<TLength>;
    /**
     * Short for `background-color` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    bgc?: CSS.BackgroundColorProperty;
    /**
     * Short for `background-image` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    bgi?: CSS.BackgroundImageProperty;
    /**
     * Short for `background-repeat` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    bgr?: CSS.BackgroundRepeatProperty;
    /**
     * Short for `background-attachment` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    bga?: CSS.BackgroundAttachmentProperty;
    /**
     * Short for `background-position` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    bgp?: CSS.BackgroundPositionProperty<TLength>;
    /**
     * Short for `background-position-x` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    bgpx?: CSS.BackgroundPositionXProperty<TLength>;
    /**
     * Short for `background-position-y` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    bgpy?: CSS.BackgroundPositionYProperty<TLength>;
    /**
     * Short for `background-clip` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    bgcp?: CSS.BackgroundClipProperty;
    /**
     * Short for `background-origin` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    bgo?: CSS.BackgroundOriginProperty;
    /**
     * Short for `background-size` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    bgsz?: CSS.BackgroundSizeProperty<TLength>;
    // Color; //
    /**
     * Short for `color` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    c?: CSS.ColorProperty;
    /**
     * Short for `opacity` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    op?: CSS.GlobalsNumber;
    // Generated Content; //
    /**
     * Short for `content` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    ct?: CSS.ContentProperty;
    /**
     * Short for `quotes` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    q?: CSS.QuotesProperty;
    /**
     * Short for `counter-increment` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    coi?: CSS.CounterIncrementProperty;
    /**
     * Short for `counter-reset` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    cor?: CSS.CounterResetProperty;
    // Outline; //
    /**
     * Short for `outline` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    ol?: CSS.OutlineProperty<TLength>;
    /**
     * Short for `outline-offset` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    olo?: CSS.OutlineOffsetProperty<TLength>;
    /**
     * Short for `outline-width` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    olw?: CSS.OutlineWidthProperty<TLength>;
    /**
     * Short for `outline-style` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    ols?: CSS.OutlineStyleProperty;
    /**
     * Short for `outline-color` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    olc?: CSS.OutlineColorProperty;
    // Tables; //
    /**
     * Short for `table-layout` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    tbl?: CSS.TableLayoutProperty;
    /**
     * Short for `caption-side` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    cps?: CSS.CaptionSideProperty;
    /**
     * Short for `empty-cells` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    ec?: CSS.EmptyCellsProperty;
    // Border;
    /**
     * Short for `border` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    bd?: CSS.BorderProperty<TLength>;
    /**
     * Short for `position` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    bdcl?: CSS.BorderCollapseProperty;
    /**
     * Short for `position` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    bdc?: CSS.BorderColorProperty;
    /**
     * Short for `position` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    bdi?: CSS.BorderImageProperty;
    /**
     * Short for `border-style` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    bds?: CSS.BorderStyleProperty;
    /**
     * Short for `border-width` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    bdw?: CSS.BorderWidthProperty<TLength>;
    /**
     * Short for `border-top` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    bdt?: CSS.BorderTopProperty<TLength>;
    /**
     * Short for `border-top-width` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    bdtw?: CSS.BorderTopWidthProperty<TLength>;
    /**
     * Short for `border-top-style` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    bdts?: CSS.BorderTopStyleProperty;
    /**
     * Short for `border-top-color` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    bdtc?: CSS.BorderTopColorProperty;
    /**
     * Short for `border-right` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    bdr?: CSS.BorderRightProperty<TLength>;
    /**
     * Short for `border-right-width` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    bdrw?: CSS.BorderRightWidthProperty<TLength>;
    /**
     * Short for `border-right-style` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    bdrst?: CSS.BorderRightStyleProperty;
    /**
     * Short for `border-right-color` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    bdrc?: CSS.BorderRightColorProperty;
    /**
     * Short for `border-bottom` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    bdb?: CSS.BorderBottomProperty<TLength>;
    /**
     * Short for `border-bottom-width` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    bdbw?: CSS.BorderBottomWidthProperty<TLength>;
    /**
     * Short for `border-bottom-style` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    bdbs?: CSS.BorderBottomStyleProperty;
    /**
     * Short for `border-bottom-color` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    bdbc?: CSS.BorderBottomColorProperty;
    /**
     * Short for `border-left` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    bdl?: CSS.BorderLeftProperty<TLength>;
    /**
     * Short for `border-left-width` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    bdlw?: CSS.BorderLeftWidthProperty<TLength>;
    /**
     * Short for `border-left-style` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    bdls?: CSS.BorderLeftStyleProperty;
    /**
     * Short for `border-left-color` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    bdlc?: CSS.BorderLeftColorProperty;
    /**
     * Short for `border-radius` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    bdrs?: CSS.BorderRadiusProperty<TLength>;
    /**
     * Short for `border-top-left-radius` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    bdtlrs?: CSS.BorderTopLeftRadiusProperty<TLength>;
    /**
     * Short for `border-top-right-radius` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    bdtrrs?: CSS.BorderTopRightRadiusProperty<TLength>;
    /**
     * Short for `border-bottom-right-radius` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    bdbrrs?: CSS.BorderBottomRightRadiusProperty<TLength>;
    /**
     * Short for `border-bottom-left-radius` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    bdblrs?: CSS.BorderBottomLeftRadiusProperty<TLength>;
    // Lists; //
    /**
     * Short for `list-style` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    lis?: CSS.ListStyleProperty;
    /**
     * Short for `list-style-position` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    lisp?: CSS.ListStylePositionProperty;
    /**
     * Short for `list-style-type` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    list?: CSS.ListStyleTypeProperty;
    /**
     * Short for `list-style-image` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    lisi?: CSS.ListStyleImageProperty;
    // Flexbox Parent/Child Properties; //
    /**
     * Short for `align-content` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    ac?: CSS.AlignContentProperty;
    /**
     * Short for `align-items` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    ai?: CSS.AlignItemsProperty;
    /**
     * Short for `align-self` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    as?: CSS.AlignSelfProperty;
    /**
     * Short for `justify-content` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    jc?: CSS.JustifyContentProperty;
    /**
     * Short for `flex` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    fx?: CSS.FlexProperty<TLength>;
    /**
     * Short for `flex-basis` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    fxb?: CSS.FlexBasisProperty<TLength>;
    /**
     * Short for `flex-direction` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    fxd?: CSS.FlexDirectionProperty;
    /**
     * Short for `flex-flow` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    fxf?: CSS.FlexFlowProperty;
    /**
     * Short for `flex-grow` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    fxg?: CSS.GlobalsNumber;
    /**
     * Short for `position` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    fxs?: CSS.GlobalsNumber;
    /**
     * Short for `flex-wrap` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    fxw?: CSS.FlexWrapProperty;
    /**
     * Short for `order` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    ord?: CSS.GlobalsNumber;
    // CSS Grid Layout; //
    /**
     * Short for `columns` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    colm?: CSS.ColumnsProperty<TLength>;
    /**
     * Short for `column-count` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    colmc?: CSS.ColumnCountProperty;
    /**
     * Short for `column-fill` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    colmf?: CSS.ColumnFillProperty;
    /**
     * Short for `column-gap` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    colmg?: CSS.ColumnGapProperty<TLength>;
    /**
     * Short for `column-rule` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    colmr?: CSS.ColumnRuleProperty<TLength>;
    /**
     * Short for `column-rule-color` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    colmrc?: CSS.ColumnRuleColorProperty;
    /**
     * Short for `column-rule-style` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    colmrs?: CSS.ColumnRuleStyleProperty;
    /**
     * Short for `column-rule-width` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    colmrw?: CSS.ColumnRuleWidthProperty<TLength>;
    /**
     * Short for `column-span` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    colms?: CSS.ColumnSpanProperty;
    /**
     * Short for `column-width` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    colmw?: CSS.ColumnWidthProperty<TLength>;
    // CSS Transitions; //
    /**
     * Short for `transform` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    trf?: CSS.TransformProperty;
    /**
     * Short for `transform-origin` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    trfo?: CSS.TransformOriginProperty<TLength>;
    /**
     * Short for `transform-style` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    trfs?: CSS.TransformStyleProperty;
    /**
     * Short for `transition` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    trs?: CSS.TransitionProperty;
    /**
     * Short for `transition-delay` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    trsde?: CSS.GlobalsString;
    /**
     * Short for `transition-duration` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    trsdu?: CSS.GlobalsString;
    /**
     * Short for `transition-property` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    trsp?: CSS.TransitionPropertyProperty;
    /**
     * Short for `transition-timing-function` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    trstf?: CSS.TransitionTimingFunctionProperty;
    // Others; //
    /**
     * Short for `backface-visibility` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    bfv?: CSS.BackfaceVisibilityProperty;
    /**
     * Short for `text-overflow` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    tov?: CSS.TextOverflowProperty;
    /**
     * Short for `orientation` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    ori?: CSS.ViewportOrientationProperty;
    /**
     * Short for `user-select` property. Requires [`atoms` addon](https://github.com/streamich/nano-css/blob/master/docs/atoms.md).
     */
    us?: CSS.UserSelectProperty;
}

export function addon(nano: NanoRenderer);
