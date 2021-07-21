"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
var debugInfo = function (context, ctx, lineSeparator) {
    var result = '';
    if (context.dumpLineNumbers && !context.compress) {
        switch (context.dumpLineNumbers) {
            case 'comments':
                result = debugInfo.asComment(ctx);
                break;
            case 'mediaquery':
                result = debugInfo.asMediaQuery(ctx);
                break;
            case 'all':
                result = debugInfo.asComment(ctx) + (lineSeparator || '') + debugInfo.asMediaQuery(ctx);
                break;
        }
    }
    return result;
};
debugInfo.asComment = function (ctx) { return ctx.debugInfo ? "/* line " + ctx.debugInfo.lineNumber + ", " + ctx.debugInfo.fileName + " */\n" : ''; };
debugInfo.asMediaQuery = function (ctx) {
    if (!ctx.debugInfo) {
        return '';
    }
    var filenameWithProtocol = ctx.debugInfo.fileName;
    if (!/^[a-z]+:\/\//i.test(filenameWithProtocol)) {
        filenameWithProtocol = "file://" + filenameWithProtocol;
    }
    return "@media -sass-debug-info{filename{font-family:" + filenameWithProtocol.replace(/([.:\/\\])/g, function (a) {
        if (a == '\\') {
            a = '\/';
        }
        return "\\" + a;
    }) + "}line{font-family:\\00003" + ctx.debugInfo.lineNumber + "}}\n";
};
exports.default = debugInfo;
//# sourceMappingURL=debug-info.js.map