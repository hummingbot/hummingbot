import { TSESTree } from '../../ts-estree';
declare const isArrowToken: (token: TSESTree.Token) => token is TSESTree.PunctuatorToken & {
    value: "=>";
};
declare const isNotArrowToken: (token: TSESTree.Token) => boolean;
declare const isClosingBraceToken: (token: TSESTree.Token) => token is TSESTree.PunctuatorToken & {
    value: "}";
};
declare const isNotClosingBraceToken: (token: TSESTree.Token) => boolean;
declare const isClosingBracketToken: (token: TSESTree.Token) => token is TSESTree.PunctuatorToken & {
    value: "]";
};
declare const isNotClosingBracketToken: (token: TSESTree.Token) => boolean;
declare const isClosingParenToken: (token: TSESTree.Token) => token is TSESTree.PunctuatorToken & {
    value: ")";
};
declare const isNotClosingParenToken: (token: TSESTree.Token) => boolean;
declare const isColonToken: (token: TSESTree.Token) => token is TSESTree.PunctuatorToken & {
    value: ":";
};
declare const isNotColonToken: (token: TSESTree.Token) => boolean;
declare const isCommaToken: (token: TSESTree.Token) => token is TSESTree.PunctuatorToken & {
    value: ",";
};
declare const isNotCommaToken: (token: TSESTree.Token) => boolean;
declare const isCommentToken: (token: TSESTree.Token) => token is TSESTree.Comment;
declare const isNotCommentToken: <T extends TSESTree.Token>(token: T) => token is Exclude<T, TSESTree.Comment>;
declare const isOpeningBraceToken: (token: TSESTree.Token) => token is TSESTree.PunctuatorToken & {
    value: "{";
};
declare const isNotOpeningBraceToken: (token: TSESTree.Token) => boolean;
declare const isOpeningBracketToken: (token: TSESTree.Token) => token is TSESTree.PunctuatorToken & {
    value: "[";
};
declare const isNotOpeningBracketToken: (token: TSESTree.Token) => boolean;
declare const isOpeningParenToken: (token: TSESTree.Token) => token is TSESTree.PunctuatorToken & {
    value: "(";
};
declare const isNotOpeningParenToken: (token: TSESTree.Token) => boolean;
declare const isSemicolonToken: (token: TSESTree.Token) => token is TSESTree.PunctuatorToken & {
    value: ";";
};
declare const isNotSemicolonToken: (token: TSESTree.Token) => boolean;
export { isArrowToken, isClosingBraceToken, isClosingBracketToken, isClosingParenToken, isColonToken, isCommaToken, isCommentToken, isNotArrowToken, isNotClosingBraceToken, isNotClosingBracketToken, isNotClosingParenToken, isNotColonToken, isNotCommaToken, isNotCommentToken, isNotOpeningBraceToken, isNotOpeningBracketToken, isNotOpeningParenToken, isNotSemicolonToken, isOpeningBraceToken, isOpeningBracketToken, isOpeningParenToken, isSemicolonToken, };
//# sourceMappingURL=predicates.d.ts.map