from hummingbot.connector.test_support.mock_paper_exchange import MockPaperExchange


class MockPurePythonPaperExchange(MockPaperExchange):

    @property
    def name(self) -> str:
        return "MockPurePythonPaperExchange"
