import fs from 'fs';
import yaml from 'js-yaml';

export namespace SwaggerManager {
  export function validateMainFile(o: any): boolean {
    return (
      'swagger' in o &&
      'info' in o &&
      'host' in o &&
      'tags' in o &&
      'schemes' in o &&
      'externalDocs' in o
    );
  }

  export function validateRoutesFile(o: any): boolean {
    return 'paths' in o;
  }

  export function validateDefinitionsFile(o: any): boolean {
    return 'definitions' in o;
  }

  export function validate(
    fp: string,
    f: (o: any) => boolean
  ): Record<any, any> {
    const o = yaml.load(fs.readFileSync(fp, 'utf8'));
    if (o != null && typeof o === 'object' && f(o)) {
      return <Record<any, any>>o;
    } else {
      throw new Error(fp + ' does not conform to the expected structure.');
    }
  }

  export function generateSwaggerJson(
    mainFilePath: string,
    definitionsFilePath: string,
    routesFilePaths: string[]
  ): Record<string, any> {
    const main = validate(mainFilePath, validateMainFile);

    const paths: Record<string, any> = {};

    for (const fp of routesFilePaths) {
      const routes = validate(fp, validateRoutesFile);
      for (const key in routes['paths']) {
        paths[key] = routes['paths'][key];
      }
    }

    main['paths'] = paths;

    const definitions = validate(definitionsFilePath, validateDefinitionsFile);
    main['definitions'] = definitions['definitions'];

    return main;
  }
}
