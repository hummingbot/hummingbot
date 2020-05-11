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
        f"{str(int(1 * UNIT_MULTIPLIER))} cGLD => {str(int(10.2 * UNIT_MULTIPLIER))} cUSD\n"
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
        "txHash: 0x7282127186c58d24657821ba00cfe20337774c820355ce568e9b7d13e0e55ec7\n"
}
