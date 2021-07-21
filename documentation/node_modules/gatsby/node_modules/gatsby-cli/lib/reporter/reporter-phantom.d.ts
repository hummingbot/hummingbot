import { Span } from "opentracing";
interface ICreatePhantomReporterArguments {
    text: string;
    id: string;
    span: Span;
}
export interface IPhantomReporter {
    start(): void;
    end(): void;
    span: Span;
}
export declare const createPhantomReporter: ({ text, id, span, }: ICreatePhantomReporterArguments) => IPhantomReporter;
export {};
