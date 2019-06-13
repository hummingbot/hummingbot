#!/usr/bin/env python

from sqlalchemy.ext.declarative import declarative_base

HummingbotBase = declarative_base()


def get_declarative_base():
    return HummingbotBase
