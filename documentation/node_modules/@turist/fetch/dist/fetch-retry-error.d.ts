import { Response } from 'node-fetch';
export default class FetchRetryError extends Error {
    res: Response;
    url: string;
    statusCode: number;
    constructor(res: Response);
}
