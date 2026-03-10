"""
Custom pagination classes for the SupplyFlow API.
"""

from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class StandardResultsSetPagination(PageNumberPagination):
    """
    Default pagination used across all list endpoints.

    Supports query parameters:
        - page: page number (1-indexed)
        - page_size: items per page (default 25, max 100)
    """

    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100
    page_query_param = "page"

    def get_paginated_response(self, data):
        return Response(
            {
                "count": self.page.paginator.count,
                "total_pages": self.page.paginator.num_pages,
                "current_page": self.page.number,
                "page_size": self.get_page_size(self.request),
                "next": self.get_next_link(),
                "previous": self.get_previous_link(),
                "results": data,
            }
        )

    def get_paginated_response_schema(self, schema):
        return {
            "type": "object",
            "required": ["count", "results"],
            "properties": {
                "count": {
                    "type": "integer",
                    "description": "Total number of items across all pages.",
                },
                "total_pages": {
                    "type": "integer",
                    "description": "Total number of pages.",
                },
                "current_page": {
                    "type": "integer",
                    "description": "Current page number.",
                },
                "page_size": {
                    "type": "integer",
                    "description": "Number of items on this page.",
                },
                "next": {
                    "type": "string",
                    "nullable": True,
                    "format": "uri",
                    "description": "URL for the next page.",
                },
                "previous": {
                    "type": "string",
                    "nullable": True,
                    "format": "uri",
                    "description": "URL for the previous page.",
                },
                "results": schema,
            },
        }


class LargeResultsSetPagination(PageNumberPagination):
    """Pagination for endpoints that may return large datasets (e.g. analytics)."""

    page_size = 100
    page_size_query_param = "page_size"
    max_page_size = 500

    def get_paginated_response(self, data):
        return Response(
            {
                "count": self.page.paginator.count,
                "total_pages": self.page.paginator.num_pages,
                "current_page": self.page.number,
                "page_size": self.get_page_size(self.request),
                "next": self.get_next_link(),
                "previous": self.get_previous_link(),
                "results": data,
            }
        )
