import { SwaggerManager } from '../../src/services/swagger-manager';
import { patch, unpatch } from './patch';
import fs from 'fs';

import 'jest-extended';

describe('validateMainFile', () => {
  it('true with all expected keys', () => {
    expect(
      SwaggerManager.validateMainFile({
        swagger: '',
        info: '',
        host: '',
        tags: '',
        schemes: '',
        externalDocs: '',
      })
    ).toEqual(true);
  });
  it('false with a key missing', () => {
    expect(
      SwaggerManager.validateMainFile({
        info: '',
        host: '',
        tags: '',
        schemes: '',
        externalDocs: '',
      })
    ).toEqual(false);
  });
});

describe('validateRoutesFile', () => {
  it('true with all expected keys', () => {
    expect(
      SwaggerManager.validateRoutesFile({
        paths: '',
      })
    ).toEqual(true);
  });
  it('false with a key missing', () => {
    expect(
      SwaggerManager.validateRoutesFile({
        info: '',
      })
    ).toEqual(false);
  });
});

describe('validateDefinitionsFile', () => {
  it('true with all expected keys', () => {
    expect(
      SwaggerManager.validateDefinitionsFile({
        definitions: '',
      })
    ).toEqual(true);
  });
  it('false with a key missing', () => {
    expect(
      SwaggerManager.validateDefinitionsFile({
        info: '',
      })
    ).toEqual(false);
  });
});

describe('validate', () => {
  afterEach(() => {
    unpatch();
  });

  it('return object if validation function returns true', () => {
    patch(fs, 'readFileSync', () => 'definitions: abc');
    expect(
      SwaggerManager.validate(
        'dummy-file-name',
        SwaggerManager.validateDefinitionsFile
      )
    ).toEqual({ definitions: 'abc' });
  });

  it('throws an error if validation function returns false', () => {
    patch(fs, 'readFileSync', () => 'definitions: abc');
    expect(() =>
      SwaggerManager.validate(
        'dummy-file-name',
        SwaggerManager.validateMainFile
      )
    ).toThrow();
  });
});

describe('generateSwaggerJson', () => {
  afterEach(() => {
    unpatch();
  });

  it('return object if validation function returns true', () => {
    patch(fs, 'readFileSync', (fp: string) => {
      if (fp === 'main') {
        return "swagger: two\ninfo: 'nothing'\nhost:  'localhost'\ntags:  []\nschemes: []\nexternalDocs: ''";
      } else if (fp === 'definitions') {
        return 'definitions: []';
      }
      return 'paths:\n  /eth:\n    get';
    });
    expect(
      SwaggerManager.generateSwaggerJson('main', 'definitions', ['path'])
    ).toEqual({
      swagger: 'two',
      info: 'nothing',
      host: 'localhost',
      tags: [],
      schemes: [],
      externalDocs: '',
      definitions: [],
      paths: { '/eth': 'get' },
    });
  });

  it('throw an error if something does not conform to the structure', () => {
    patch(fs, 'readFileSync', (fp: string) => {
      if (fp === 'main') {
        return 'swagger: two\n';
      } else if (fp === 'definitions') {
        return 'definitions: []';
      }
      return 'paths:\n  /eth:\n    get';
    });
    expect(() =>
      SwaggerManager.generateSwaggerJson('main', 'definitions', ['path'])
    ).toThrow();
  });
});
