/* eslint-disable */
'use strict';

var env = require('./env');
var create = require('../../index').create;
var addonRule = require('../../addon/rule').addon;
var addonVirtual = require('../../addon/virtual').addon;
var addonKeyframes = require('../../addon/keyframes').addon;

function createNano (config) {
    var nano = create(config);

    addonRule(nano);
    addonVirtual(nano);

    return nano;
};

describe('virtual', function () {
    it('installs interface', function () {
        var nano = createNano();

        expect(typeof nano.atomic).toBe('function');
        expect(typeof nano.virtual).toBe('function');
    });

    describe('atomic()', function () {
        it('injects raw styles', function () {
            var nano = createNano();

            var className = nano.atomic('&', 'color:red;', '');

            expect(className).toBe('_a');

            if (env.isServer) {
                expect(nano.raw).toBe('._a{color:red;}');
            }
        });

        it('increments ID', function () {
            var nano = createNano();

            expect(nano.atomic('&', 'color:red;')).toBe('_a')
            expect(nano.atomic('&', 'color:blue;')).toBe('_b')
            expect(nano.atomic('&', 'color:green;')).toBe('_c')

            if (env.isServer) {
                expect(nano.raw).toBe('._a{color:red;}._b{color:blue;}._c{color:green;}');
            }
        });

        it('caches', function () {
            var nano = createNano();

            expect(nano.atomic('&', 'color:red;')).toBe('_a')
            expect(nano.atomic('&', 'color:red;')).toBe('_a')
        });

        it('at-rules', function () {
            var nano = createNano();

            expect(nano.atomic('&', 'color:red;', '@media screen')).toBe('_a')
            expect(nano.atomic('&', 'color:red;', '@media screen')).toBe('_a')

            if (env.isServer) {
                expect(nano.raw).toBe('@media screen{._a{color:red;}}');
            }
        });

        it('interpolates selector', function () {
            var nano = createNano();

            expect(nano.atomic('.global &:hover', 'color:red;', '@media screen')).toBe('_a')
            expect(nano.atomic('.global &:hover', 'color:red;', '@media screen')).toBe('_a')

            if (env.isServer) {
                expect(nano.raw).toBe('@media screen{.global ._a:hover{color:red;}}');
            }
        });

        it('prefixes class names', function () {
            var nano = createNano({
                pfx: 'foo-'
            });

            expect(nano.atomic('&', 'color:red;')).toBe('foo-a');
        });
    });

    describe('virtual()', function () {
        it('injects CSS', function () {
            var nano = createNano();
            var className = nano.virtual('&', {
                color: 'red'
            });

            expect(className).toBe(' _a');
            if (env.isServer) {
                expect(nano.raw).toBe('._a{color:red}');
            }
        });

        it('makes styles atomic', function () {
            var nano = createNano();
            var className = nano.virtual('&', {
                color: 'red',
                background: 'black',
                textAlign: 'center'
            });

            expect(className).toBe(' _a _b _c');

            if (env.isServer) {
                expect(nano.raw.includes('color:red')).toBe(true);
                expect(nano.raw.includes('background:black')).toBe(true);
                expect(nano.raw.includes('text-align:center')).toBe(true);
            }
        });

        it('allows nesting', function () {
            var nano = createNano();
            var className = nano.virtual('&', {
                color: 'red',
                ':hover': {
                    color: 'blue',
                }
            });

            expect(className).toBe(' _a _b');

            if (env.isServer) {
                expect(nano.raw.includes('._a')).toBe(true);
                expect(nano.raw.includes('._b')).toBe(true);
                expect(nano.raw.includes(':hover')).toBe(true);
                expect(nano.raw.includes('color:red')).toBe(true);
                expect(nano.raw.includes('color:blue')).toBe(true);
            }
        });

        it('multiple styles', function () {
            var nano = createNano();

            nano.atomic = jest.fn();

            var className = nano.virtual('&', {
                color: 'tomato',
                border: '1px solid red',
                margin: '10px auto',
                padding: '0',
                ':focus': {
                    color: 'blue',
                },
                '@media screen': {
                    textAlign: 'right',
                    cursor: 'pointer',
                }
            });

            expect(nano.atomic).toHaveBeenCalledWith('&', 'color:tomato', undefined);
            expect(nano.atomic).toHaveBeenCalledWith('&', 'border:1px solid red', undefined);
            expect(nano.atomic).toHaveBeenCalledWith('&', 'margin:10px auto', undefined);
            expect(nano.atomic).toHaveBeenCalledWith('&', 'padding:0', undefined);
            expect(nano.atomic).toHaveBeenCalledWith('&:focus', 'color:blue', undefined);
            expect(nano.atomic).not.toHaveBeenCalledWith('&:focus', 'color:tomato', undefined);
            expect(nano.atomic).toHaveBeenCalledWith('&', 'text-align:right', '@media screen');
            expect(nano.atomic).toHaveBeenCalledWith('&', 'cursor:pointer', '@media screen');
            expect(nano.atomic).not.toHaveBeenCalledWith('&', 'color:tomato', '@media screen');
        });

        it('extrapolates array values', function () {
            var nano = createNano();

            nano.atomic = jest.fn();

            var className = nano.virtual('&', {
                color: 'blue;color:red;',
            });

            expect(nano.atomic).toHaveBeenCalledTimes(2);
            expect(nano.atomic).toHaveBeenCalledWith('&', 'color:blue', undefined);
            expect(nano.atomic).toHaveBeenCalledWith('&', 'color:red', undefined);
        });

        it('removes semicolons', function () {
            var nano = createNano();

            nano.atomic = jest.fn();

            var className = nano.virtual('&', {
                color: 'blue;;;;;',
            });

            expect(nano.atomic).toHaveBeenCalledTimes(1);
            expect(nano.atomic).toHaveBeenCalledWith('&', 'color:blue', undefined);
        });

	    it('doesn\'t break keyframes', function() {
		    var nano = createNano();
            addonKeyframes(nano);

		    nano.virtual('&', {
			    animation: 'sk-foldCubeAngle 2.4s infinite linear both',
			    '@keyframes sk-foldCubeAngle': {
				    '0%, 10%': {
					    transform: 'perspective(140px) rotateX(-180deg)',
					    opacity: 0
				    },
				    '25%, 75%': {
					    transform: 'perspective(140px) rotateX(0deg)',
					    opacity: 1
				    },
				    '90%, 100%': {
					    transform: 'perspective(140px) rotateY(180deg)',
					    opacity: 0
				    }
			    }
		    });

		    if (env.isServer) {
			    expect(nano.raw).toEqual('._a{animation:sk-foldCubeAngle 2.4s infinite linear both}@-webkit-keyframes sk-foldCubeAngle{0%, 10%{transform:perspective(140px) rotateX(-180deg);opacity:0;}25%, 75%{transform:perspective(140px) rotateX(0deg);opacity:1;}90%, 100%{transform:perspective(140px) rotateY(180deg);opacity:0;}}@-moz-keyframes sk-foldCubeAngle{0%, 10%{transform:perspective(140px) rotateX(-180deg);opacity:0;}25%, 75%{transform:perspective(140px) rotateX(0deg);opacity:1;}90%, 100%{transform:perspective(140px) rotateY(180deg);opacity:0;}}@-o-keyframes sk-foldCubeAngle{0%, 10%{transform:perspective(140px) rotateX(-180deg);opacity:0;}25%, 75%{transform:perspective(140px) rotateX(0deg);opacity:1;}90%, 100%{transform:perspective(140px) rotateY(180deg);opacity:0;}}@keyframes sk-foldCubeAngle{0%, 10%{transform:perspective(140px) rotateX(-180deg);opacity:0;}25%, 75%{transform:perspective(140px) rotateX(0deg);opacity:1;}90%, 100%{transform:perspective(140px) rotateY(180deg);opacity:0;}}');

		    }
	    });
    });
});
