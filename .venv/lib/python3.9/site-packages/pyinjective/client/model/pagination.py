import base64
from typing import Optional

from pyinjective.proto.cosmos.base.query.v1beta1 import pagination_pb2 as pagination_pb


class PaginationOption:
    def __init__(
        self,
        encoded_page_key: Optional[str] = None,
        skip: Optional[int] = None,
        limit: Optional[int] = None,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        reverse: Optional[bool] = None,
        count_total: Optional[bool] = None,
        from_number: Optional[int] = None,
        to_number: Optional[int] = None,
    ):
        super().__init__()
        self.encoded_page_key = encoded_page_key
        self.skip = skip
        self.limit = limit
        self.start_time = start_time
        self.end_time = end_time
        self.reverse = reverse
        self.count_total = count_total
        self.from_number = from_number
        self.to_number = to_number

    def create_pagination_request(self) -> pagination_pb.PageRequest:
        page_request = pagination_pb.PageRequest()

        if self.encoded_page_key is not None and self.encoded_page_key != "":
            page_key = base64.b64decode(self.encoded_page_key)
            page_request.key = page_key
        if self.skip is not None:
            page_request.offset = self.skip
        if self.limit is not None:
            page_request.limit = self.limit
        if self.reverse is not None:
            page_request.reverse = self.reverse
        if self.count_total is not None:
            page_request.count_total = self.count_total

        return page_request


class Pagination:
    def __init__(
        self,
        next: Optional[str] = None,
        total: Optional[int] = None,
    ):
        super().__init__()
        self.next = next
        self.total = total

    @classmethod
    def from_proto(cls, proto_pagination: pagination_pb.PageResponse):
        next = None

        if proto_pagination.next_key is not None:
            next = f"0x{proto_pagination.next_key.hex()}"
        total = proto_pagination.total

        return cls(
            next=next,
            total=total,
        )
