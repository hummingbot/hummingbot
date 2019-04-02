#!/usr/bin/env python

from typing import Tuple
import pandas as pd


class OrderBookUtils:
    @staticmethod
    def get_compare_df(book_1: pd.DataFrame, book_2: pd.DataFrame,
                       n_rows: int = 200, diffs_only: bool = False) -> pd.DataFrame:
        book_1: pd.DataFrame = book_1.copy()
        book_2: pd.DataFrame = book_2.copy()
        book_1.index = book_1.price
        book_2.index = book_2.price
        compare_df: pd.DataFrame = pd.concat([book_1.iloc[0:n_rows], book_2.iloc[0:n_rows]],
                                             axis="columns", keys=["pre", "post"])

        if not diffs_only:
            return compare_df
        else:
            compare_df = compare_df.fillna(0.0)
            return compare_df[(compare_df["pre"]["amount"] - compare_df["post"]["amount"]).abs() > 1e-8]

    @staticmethod
    def compare_books(book_1: pd.DataFrame, book_2: pd.DataFrame, n_rows: int = 200) -> Tuple[int, int]:
        """
        :param book_1: First book
        :param book_2: Second book
        :param n_rows: Number of top entries to compare.
        :return: (# of matching entries, # of total entries)
        """
        compare_df: pd.DataFrame = OrderBookUtils.get_compare_df(book_1, book_2, n_rows)
        matching_rows: int = 0
        total_rows: int = 0

        for row in compare_df.itertuples():
            total_rows += 1
            if abs(row._1 - row._4) < 1e-8 and abs(row._2 - row._5) < 1e-8:
                matching_rows += 1

        return matching_rows, total_rows
