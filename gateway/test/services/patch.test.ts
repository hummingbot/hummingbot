import { patch, unpatch } from './patch';
import 'jest-extended';

class A {
  private _x: number = 0;

  public get x() {
    return this._x;
  }

  private _y: boolean = false;

  public get y() {
    return this._y;
  }

  private _z: string = 'Guten Tag';

  public get z() {
    return this._z;
  }
}

class B {
  private _alter: (x: string) => string = (x) => x.toLowerCase();

  public get alter() {
    return this._alter;
  }
}

describe('internal patch system', () => {
  it('It can patch and unpatch private variables', () => {
    const a = new A();
    // _x is private
    patch(a, '_x', 1);
    expect(a.x).toEqual(1);

    unpatch();
    expect(a.x).toEqual(0);
  });

  it('It can patch a value multiple times and then retrieve the original value', () => {
    const a = new A();
    patch(a, '_x', 1);
    expect(a.x).toEqual(1);

    patch(a, '_x', 3);
    expect(a.x).toEqual(3);

    patch(a, '_x', 10);
    expect(a.x).toEqual(10);

    unpatch();
    expect(a.x).toEqual(0);
  });

  it('It can patch multiple values on an object and then retrieve all the original values', () => {
    const a = new A();
    patch(a, '_x', 178);
    patch(a, '_y', true);
    patch(a, '_z', 'Guten Nacht');
    expect(a.x).toEqual(178);
    expect(a.y).toEqual(true);
    expect(a.z).toEqual('Guten Nacht');

    patch(a, '_x', 999);
    patch(a, '_z', 'Hummingbot');
    expect(a.x).toEqual(999);
    expect(a.z).toEqual('Hummingbot');

    unpatch();
    expect(a.x).toEqual(0);
    expect(a.y).toEqual(false);
    expect(a.z).toEqual('Guten Tag');
  });

  it('It can patch and unpatch methods', () => {
    const b = new B();
    // '_alter' is private
    patch(b, '_alter', (x: string) => x.toUpperCase());
    expect(b.alter('HeLlO')).toEqual('HELLO');

    unpatch();
    expect(b.alter('HeLlO')).toEqual('hello');
  });
});
