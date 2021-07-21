"use strict";

exports.__esModule = true;
exports.programReducer = void 0;

var _reporter = require("gatsby-cli/lib/reporter/reporter");

const initialState = {
  directory: `/`,
  status: `BOOTSTRAPPING`,
  _: `develop`,
  useYarn: false,
  open: false,
  openTracingConfigFile: ``,
  port: 80,
  proxyPort: 80,
  host: `localhost`,
  sitePackageJson: {},
  extensions: [],
  report: _reporter.reporter
};

const programReducer = (state = initialState, action) => {
  switch (action.type) {
    case `SET_PROGRAM`:
      return { ...action.payload
      };

    case `SET_PROGRAM_EXTENSIONS`:
      return { ...state,
        extensions: action.payload
      };

    case `SET_PROGRAM_STATUS`:
      return { ...state,
        status: `BOOTSTRAP_FINISHED`
      };

    default:
      return state;
  }
};

exports.programReducer = programReducer;
//# sourceMappingURL=program.js.map