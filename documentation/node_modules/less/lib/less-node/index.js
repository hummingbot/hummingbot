"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
var environment_1 = __importDefault(require("./environment"));
var file_manager_1 = __importDefault(require("./file-manager"));
var url_file_manager_1 = __importDefault(require("./url-file-manager"));
var less_1 = __importDefault(require("../less"));
var lessc_helper_1 = __importDefault(require("./lessc-helper"));
var plugin_loader_1 = __importDefault(require("./plugin-loader"));
var fs_1 = __importDefault(require("./fs"));
var default_options_1 = __importDefault(require("../less/default-options"));
var image_size_1 = __importDefault(require("./image-size"));
var less = less_1.default(environment_1.default, [new file_manager_1.default(), new url_file_manager_1.default()]);
// allow people to create less with their own environment
less.createFromEnvironment = less_1.default;
less.lesscHelper = lessc_helper_1.default;
less.PluginLoader = plugin_loader_1.default;
less.fs = fs_1.default;
less.FileManager = file_manager_1.default;
less.UrlFileManager = url_file_manager_1.default;
// Set up options
less.options = default_options_1.default();
// provide image-size functionality
image_size_1.default(less.environment);
exports.default = less;
//# sourceMappingURL=index.js.map