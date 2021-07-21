import { ErrorId, IErrorMapEntry } from "./error-map";
import { IConstructError, IStructuredError } from "./types";
declare const constructError: ({ details: { id, ...otherDetails } }: IConstructError, suppliedErrorMap: Record<ErrorId, IErrorMapEntry>) => IStructuredError;
export default constructError;
