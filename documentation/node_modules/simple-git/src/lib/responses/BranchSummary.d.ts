import { BranchSummary, BranchSummaryBranch } from '../../../typings';
export declare class BranchSummaryResult implements BranchSummary {
    all: string[];
    branches: {
        [p: string]: BranchSummaryBranch;
    };
    current: string;
    detached: boolean;
    push(current: boolean, detached: boolean, name: string, commit: string, label: string): void;
}
