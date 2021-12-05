import { SwaggerManager } from '../../src/services/swagger-manager';
import { patch, unpatch } from './patch';
// import yaml from 'js-yaml';
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
