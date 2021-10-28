module.exports = {
  preset: 'ts-jest',
  testEnvironment: 'node',
  modulePathIgnorePatterns: ['<rootDir>/dist/'],
  detectOpenHandles: true,
  coveragePathIgnorePatterns: [
    'src/app.ts',
    'src/services/ethereum-base.ts',
    'src/services/chains/ethereum/ethereum.ts',
    'src/services/chains/ethereum/uniswap/uniswap.ts',
  ],
  moduleFileExtensions: ['ts', 'tsx', 'js'],
  transform: {
    '^.+\\.(ts|tsx)$': 'ts-jest',
  },
  globals: {
    'ts-jest': {
      tsConfigFile: 'tsconfig.json',
    },
  },
};
