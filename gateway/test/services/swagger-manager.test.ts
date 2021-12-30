import { SwaggerManager } from '../../src/services/swagger-manager';
import { patch, unpatch } from './patch';
// import { app } from '../../src/app';
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

// describe('verify vefinitions', () => {
//   // beforeAll(() => {
//   //   unpatch();
//   // });
//   console.log(app)
//   // it('All routes should have swagger documentation', () => {
//   //   // const swaggerDocument = SwaggerManager.generateSwaggerJson(
//   //   //   '../../docs/swagger/swagger.yml',
//   //   //   '../../docs/swagger/definitions.yml',
//   //   //   [
//   //   //     '../../docs/swagger/main-routes.yml',
//   //   //     '../../docs/swagger/eth-routes.yml',
//   //   //     '../../docs/swagger/eth-uniswap-routes.yml',
//   //   //     '../../docs/swagger/avalanche-routes.yml',
//   //   //     '../../docs/swagger/avalanche-pangolin-routes.yml',
//   //   //   ]
//   //   // );
//   //   // console.log(Object.keys(swaggerDocument.paths).sort());

//   //   const routes: any[] = [];
//   //   // app._router.stack.forEach(function (middleware: any) {
//   //   //   if (middleware.route) {
//   //   //     // routes registered directly on the app
//   //   //     routes.push(middleware.route.path);
//   //   //   } else if (middleware.name === 'router') {
//   //   //     const parentPath = middleware.regexp
//   //   //       .toString()
//   //   //       .split('?')[0]
//   //   //       .slice(2)
//   //   //       .replaceAll('\\', '')
//   //   //       .slice(0, -1);
//   //   //     // router middleware
//   //   //     middleware.handle.stack.forEach(function (handler: any) {
//   //   //       const route = handler.route;
//   //   //       if (route) {
//   //   //         route.path = `${parentPath}${route.path}`;
//   //   //         routes.push(route.path);
//   //   //       }
//   //   //     });
//   //   //   }
//   //   // });
//   //   console.log('total routes', app, routes.sort());
//   // });
// });
