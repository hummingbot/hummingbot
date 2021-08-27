import fs from 'fs';
import { ConfigManager } from '../../src/services/config-manager';
import 'jest-extended';
import yaml from 'js-yaml';

test('validateConfig', () => {
  expect(
    ConfigManager.validateConfig(
      yaml.load(fs.readFileSync('conf/gateway-config-example.yml', 'utf8'))
    )
  ).toEqual(true);
});
