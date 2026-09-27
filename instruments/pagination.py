"""Stable cursor pagination for potentially large price histories."""
from rest_framework.pagination import CursorPagination


class PriceBarCursorPagination(CursorPagination):
    page_size = 100
    page_size_query_param = "page_size"
    max_page_size = 500
    ordering = ("-timestamp", "-id")
