"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    Object.defineProperty(o, k2, { enumerable: true, get: function() { return m[k]; } });
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || function (mod) {
    if (mod && mod.__esModule) return mod;
    var result = {};
    if (mod != null) for (var k in mod) if (Object.hasOwnProperty.call(mod, k)) __createBinding(result, mod, k);
    __setModuleDefault(result, mod);
    return result;
};
Object.defineProperty(exports, "__esModule", { value: true });
const TimeUnit = __importStar(require("./timeunit"));
const s = 1000;
const m = s * 60;
const h = m * 60;
const d = h * 24;
const w = d * 7;
const y = d * 365.25;
function default_1(n, type) {
    switch (type) {
        case TimeUnit.Year:
            return n * y;
        case TimeUnit.Week:
            return n * w;
        case TimeUnit.Day:
            return n * d;
        case TimeUnit.Hour:
            return n * h;
        case TimeUnit.Minute:
            return n * m;
        case TimeUnit.Second:
            return n * s;
        case TimeUnit.MilliSecond:
            return n;
        default:
            return undefined;
    }
}
exports.default = default_1;
exports.TimeUnit = __importStar(require("./timeunit"));
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiaW5kZXguanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyIuLi9zcmMvaW5kZXgudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7O0FBQUEscURBQXVDO0FBRXZDLE1BQU0sQ0FBQyxHQUFHLElBQUksQ0FBQztBQUNmLE1BQU0sQ0FBQyxHQUFHLENBQUMsR0FBRyxFQUFFLENBQUM7QUFDakIsTUFBTSxDQUFDLEdBQUcsQ0FBQyxHQUFHLEVBQUUsQ0FBQztBQUNqQixNQUFNLENBQUMsR0FBRyxDQUFDLEdBQUcsRUFBRSxDQUFDO0FBQ2pCLE1BQU0sQ0FBQyxHQUFHLENBQUMsR0FBRyxDQUFDLENBQUM7QUFDaEIsTUFBTSxDQUFDLEdBQUcsQ0FBQyxHQUFHLE1BQU0sQ0FBQztBQVdyQixtQkFBeUIsQ0FBUyxFQUFFLElBQWM7SUFDaEQsUUFBUSxJQUFJLEVBQUU7UUFDWixLQUFLLFFBQVEsQ0FBQyxJQUFJO1lBQ2hCLE9BQU8sQ0FBQyxHQUFHLENBQUMsQ0FBQztRQUNmLEtBQUssUUFBUSxDQUFDLElBQUk7WUFDaEIsT0FBTyxDQUFDLEdBQUcsQ0FBQyxDQUFDO1FBQ2YsS0FBSyxRQUFRLENBQUMsR0FBRztZQUNmLE9BQU8sQ0FBQyxHQUFHLENBQUMsQ0FBQztRQUNmLEtBQUssUUFBUSxDQUFDLElBQUk7WUFDaEIsT0FBTyxDQUFDLEdBQUcsQ0FBQyxDQUFDO1FBQ2YsS0FBSyxRQUFRLENBQUMsTUFBTTtZQUNsQixPQUFPLENBQUMsR0FBRyxDQUFDLENBQUM7UUFDZixLQUFLLFFBQVEsQ0FBQyxNQUFNO1lBQ2xCLE9BQU8sQ0FBQyxHQUFHLENBQUMsQ0FBQztRQUNmLEtBQUssUUFBUSxDQUFDLFdBQVc7WUFDdkIsT0FBTyxDQUFDLENBQUM7UUFDWDtZQUNFLE9BQU8sU0FBUyxDQUFDO0tBQ3BCO0FBQ0gsQ0FBQztBQW5CRCw0QkFtQkM7QUFFRCx1REFBdUMifQ==