#!/usr/bin/env python

from sqlalchemy import (
    Column,
    Text,
)

from . import HummingbotBase


class Metadata(HummingbotBase):
    __tablename__ = "Metadata"

    key = Column(Text, primary_key=True, nullable=False)
    value = Column(Text, nullable=False)
