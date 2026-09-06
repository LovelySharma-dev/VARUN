import type { Config } from 'jest';
import { pathsToModuleNameMapper } from 'ts-jest';
import ts from 'typescript';

const { config: tsconfig } = ts.readConfigFile(
  './tsconfig.json',
  ts.sys.readFile,
);

const paths = tsconfig?.compilerOptions?.paths ?? {};

const config: Config = {
  rootDir: '.',

  preset: 'ts-jest',

  testEnvironment: 'node',

  moduleFileExtensions: ['js', 'json', 'ts'],

  testRegex: '.*\.spec\.ts$',

  transform: {
    '^.+\.tsx?$': [
      'ts-jest',
      {
        useESM: false,
        tsconfig: './tsconfig.json',
      },
    ],
  },

  moduleNameMapper: {
    ...pathsToModuleNameMapper(paths, {
      prefix: '<rootDir>/',
    }),
  },

  collectCoverageFrom: [
    'src/**/*.(t|j)s',
    'libs/**/*.(t|j)s',
    'apps/**/*.(t|j)s',
  ],

  coverageDirectory: './coverage',

  testPathIgnorePatterns: [
    '/node_modules/',
    '/dist/',
  ],
};

export default config;
