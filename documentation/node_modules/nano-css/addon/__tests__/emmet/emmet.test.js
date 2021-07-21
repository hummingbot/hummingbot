/* eslint-disable */
'use strict';

var create = require('../../../').create;
var emmet = require('../../emmet').emmet;
var addonEmmet = require('../../emmet').addon;

it('emmet has proper key value pairs', function() {
    expect(emmet).toEqual({
        // Visual Formatting;
        pos: 'position',
        t: 'top',
        r: 'right',
        b: 'bottom',
        l: 'left',
        z: 'z-index',
        fl: 'float',
        cl: 'clear',
        d: 'display',
        v: 'visibility',
        ov: 'overflow',
        ovx: 'overflow-x',
        ovy: 'overflow-y',
        ovs: 'overflow-style',
        zm: 'zoom',
        cp: 'clip',
        rsz: 'resize',
        cur: 'cursor',
        // Margin & Padding;
        m: 'margin',
        mt: 'margin-top',
        mr: 'margin-right',
        mb: 'margin-bottom',
        ml: 'margin-left',
        p: 'padding',
        pt: 'padding-top',
        pr: 'padding-right',
        pb: 'padding-bottom',
        pl: 'padding-left',
        // Box Sizing;
        bxz: 'box-sizing',
        bxsh: 'box-shadow',
        w: 'width',
        h: 'height',
        maw: 'max-width',
        mah: 'max-height',
        miw: 'min-width',
        mih: 'min-height',
        // Font;
        f: 'font',
        fw: 'font-weight',
        fs: 'font-style',
        fv: 'font-variant',
        fz: 'font-size',
        ff: 'font-family',
        fsm: 'font-smooth',
        fst: 'font-stretch',
        // Text;
        va: 'vertical-align',
        ta: 'text-align',
        td: 'text-decoration',
        te: 'text-emphasis',
        ti: 'text-indent',
        tj: 'text-justify',
        tt: 'text-transform',
        tsh: 'text-shadow',
        lh: 'line-height',
        lts: 'letter-spacing',
        whs: 'white-space',
        wob: 'word-break',
        wos: 'word-spacing',
        wow: 'word-wrap',
        // Background;
        bg: 'background',
        bgc: 'background-color',
        bgi: 'background-image',
        bgr: 'background-repeat',
        bga: 'background-attachment',
        bgp: 'background-position',
        bgpx: 'background-position-x',
        bgpy: 'background-position-y',
        bgcp: 'background-clip',
        bgo: 'background-origin',
        bgsz: 'background-size',
        // Color;
        c: 'color',
        op: 'opacity',
        // Generated Content;
        ct: 'content',
        q: 'quotes',
        coi: 'counter-increment',
        cor: 'counter-reset',
        // Outline;
        ol: 'outline',
        olo: 'outline-offset',
        olw: 'outline-width',
        ols: 'outline-style',
        olc: 'outline-color',
        // Tables;
        tbl: 'table-layout',
        cps: 'caption-side',
        ec: 'empty-cells',
        // Border;
        bd: 'border',
        bdcl: 'border-collapse',
        bdc: 'border-color',
        bdi: 'border-image',
        bds: 'border-style',
        bdw: 'border-width',
        bdt: 'border-top',
        bdtw: 'border-top-width',
        bdts: 'border-top-style',
        bdtc: 'border-top-color',
        bdr: 'border-right',
        bdrw: 'border-right-width',
        bdrst: 'border-right-style',
        bdrc: 'border-right-color',
        bdb: 'border-bottom',
        bdbw: 'border-bottom-width',
        bdbs: 'border-bottom-style',
        bdbc: 'border-bottom-color',
        bdl: 'border-left',
        bdlw: 'border-left-width',
        bdls: 'border-left-style',
        bdlc: 'border-left-color',
        bdrs: 'border-radius',
        bdtlrs: 'border-top-left-radius',
        bdtrrs: 'border-top-right-radius',
        bdbrrs: 'border-bottom-right-radius',
        bdblrs: 'border-bottom-left-radius',
        // Lists;
        lis: 'list-style',
        lisp: 'list-style-position',
        list: 'list-style-type',
        lisi: 'list-style-image',
        // Flexbox Parent/Child Properties;
        ac: 'align-content',
        ai: 'align-items',
        as: 'align-self',
        jc: 'justify-content',
        fx: 'flex',
        fxb: 'flex-basis',
        fxd: 'flex-direction',
        fxf: 'flex-flow',
        fxg: 'flex-grow',
        fxs: 'flex-shrink',
        fxw: 'flex-wrap',
        ord: 'order',
        // CSS Grid Layout;
        colm: 'columns',
        colmc: 'column-count',
        colmf: 'column-fill',
        colmg: 'column-gap',
        colmr: 'column-rule',
        colmrc: 'column-rule-color',
        colmrs: 'column-rule-style',
        colmrw: 'column-rule-width',
        colms: 'column-span',
        colmw: 'column-width',
        // CSS Transitions;
        trf: 'transform',
        trfo: 'transform-origin',
        trfs: 'transform-style',
        trs: 'transition',
        trsde: 'transition-delay',
        trsdu: 'transition-duration',
        trsp: 'transition-property',
        trstf: 'transition-timing-function',
        // Others;
        bfv: 'backface-visibility',
        tov: 'text-overflow',
        mar: 'max-resolution',
        mir: 'min-resolution',
        ori: 'orientation',
        us: 'user-select',
    });
});

function createNano(config) {
    var nano = create(config);
    addonEmmet(nano);
    return nano;
}

describe('emmet', function() {
    it('installs without crashing', function() {
        var nano = createNano();
    });

    it('passes through standard properties', function() {
        var nano = createNano();

        nano.putRaw = jest.fn();

        nano.put('.foo', {
            color: 'red',
        });

        expect(nano.putRaw.mock.calls[0][0].includes('color:red')).toBeTruthy();
    });

    it('expands the abbreviations', function() {
        var nano = createNano();

        nano.putRaw = jest.fn();

        nano.put('.bar', {
            c: 'blue',
            ta: 'center',
            ord: '1',
            mah: '200px',
        });

        expect(nano.putRaw.mock.calls[0][0].includes('color:blue')).toBeTruthy();
        expect(nano.putRaw.mock.calls[0][0].includes('text-align:center')).toBeTruthy();
        expect(nano.putRaw.mock.calls[0][0].includes('order:1')).toBeTruthy();
        expect(nano.putRaw.mock.calls[0][0].includes('max-height:200px')).toBeTruthy();
    });
});
