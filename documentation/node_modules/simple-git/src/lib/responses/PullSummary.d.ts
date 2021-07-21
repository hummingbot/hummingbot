import { PullDetailFileChanges, PullDetailSummary, PullResult } from '../../../typings';
export declare class PullSummary implements PullResult {
    remoteMessages: {
        all: never[];
    };
    created: never[];
    deleted: string[];
    files: string[];
    deletions: PullDetailFileChanges;
    insertions: PullDetailFileChanges;
    summary: PullDetailSummary;
}
