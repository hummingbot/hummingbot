export default class MessageTypes {
    static GQL_CONNECTION_INIT: string;
    static GQL_CONNECTION_ACK: string;
    static GQL_CONNECTION_ERROR: string;
    static GQL_CONNECTION_KEEP_ALIVE: string;
    static GQL_CONNECTION_TERMINATE: string;
    static GQL_START: string;
    static GQL_DATA: string;
    static GQL_ERROR: string;
    static GQL_COMPLETE: string;
    static GQL_STOP: string;
    static SUBSCRIPTION_START: string;
    static SUBSCRIPTION_DATA: string;
    static SUBSCRIPTION_SUCCESS: string;
    static SUBSCRIPTION_FAIL: string;
    static SUBSCRIPTION_END: string;
    static INIT: string;
    static INIT_SUCCESS: string;
    static INIT_FAIL: string;
    static KEEP_ALIVE: string;
    constructor();
}
