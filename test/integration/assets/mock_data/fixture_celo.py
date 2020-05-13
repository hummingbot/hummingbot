UNIT_MULTIPLIER = 1e18
TEST_ADDRESS = 'TEST_ADDRESS'
TEST_PASSWORD = 'TEST_PASSWORD'

outputs = {
    ('celocli', 'exchange:show', '--amount', str(int(9.95 * UNIT_MULTIPLIER))):
        "Fetching exchange rates...... done\n"
        f"{str(int(9.95 * UNIT_MULTIPLIER))} cGLD => {str(int(99.5 * UNIT_MULTIPLIER))} cUSD\n"
        f"{str(int(9.95 * UNIT_MULTIPLIER))} cUSD => {str(int(1 * UNIT_MULTIPLIER))} cGLD",

    ('celocli', 'exchange:show', '--amount', str(int(1 * UNIT_MULTIPLIER))):
        "Fetching exchange rates...... done\n"
        f"{str(int(1 * UNIT_MULTIPLIER))} cGLD => {str(int(10.5 * UNIT_MULTIPLIER))} cUSD\n"
        f"{str(int(1 * UNIT_MULTIPLIER))} cUSD => {str(int(0.095 * UNIT_MULTIPLIER))} cGLD",

    ('celocli', 'exchange:show', '--amount', str(int(9.83 * 5 * UNIT_MULTIPLIER))):
        "Fetching exchange rates...... done\n"
        f"{str(int(9.83 * 5 * UNIT_MULTIPLIER))} cGLD => {str(int(99.5 * 5 * UNIT_MULTIPLIER))} cUSD\n"
        f"{str(int(9.83 * 5 * UNIT_MULTIPLIER))} cUSD => {str(int(0.99 * 5 * UNIT_MULTIPLIER))} cGLD",

    ('celocli', 'exchange:show', '--amount', str(int(5 * UNIT_MULTIPLIER))):
        "Fetching exchange rates...... done\n"
        f"{str(int(5 * UNIT_MULTIPLIER))} cGLD => {str(int(10.1 * 5 * UNIT_MULTIPLIER))} cUSD\n"
        f"{str(int(5 * UNIT_MULTIPLIER))} cUSD => {str(int(0.095 * 5 * UNIT_MULTIPLIER))} cGLD",

    ('celocli', 'account:unlock', TEST_ADDRESS, '--password', TEST_PASSWORD):
        "",

    ('celocli', 'exchange:gold', '--from', TEST_ADDRESS, '--value', str(int(1 * UNIT_MULTIPLIER))):
        "Sending Transaction: increaseAllowance... done\n"
        "SendTransaction: increaseAllowance\n"
        "txHash: 0xfd0777b214f4993c8f182e3d90ce15cee9db59aa0ec48621c68dadc880316c0e\n"
        "Sending Transaction: exchange... done\n"
        "SendTransaction: exchange\n"
        "txHash: 0xTEST_TX_HASSHHHHHHHHHHH\n",

    ('celocli', 'exchange:dollars', '--from', TEST_ADDRESS, '--value', str(int(1 * UNIT_MULTIPLIER))):
        "SendTransaction: increaseAllowance\n"
        "txHash: 0xc01bdc3a8059a26519db0448d05fbf585cc63bb1a762e0da1b94f2a118ca4035\n"
        "Sending Transaction: increaseAllowance... done\n"
        "SendTransaction: exchange\n"
        "txHash: 0xTEST_TX_HASSHHHHHHHHHHH\n"
        "Sending Transaction: exchange... done"
}
