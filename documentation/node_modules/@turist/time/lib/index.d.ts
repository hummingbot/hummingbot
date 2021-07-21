import * as TimeUnit from './timeunit';
declare type TimeUnit = typeof TimeUnit.Year | typeof TimeUnit.Week | typeof TimeUnit.Day | typeof TimeUnit.Hour | typeof TimeUnit.Minute | typeof TimeUnit.Second | typeof TimeUnit.MilliSecond;
export default function (n: number, type: TimeUnit): number | undefined;
export * as TimeUnit from './timeunit';
