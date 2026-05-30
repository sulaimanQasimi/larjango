from __future__ import annotations

from django.core.paginator import Paginator


def paginate(request, queryset, per_page: int = 15, page_name: str = "page"):
    paginator = Paginator(queryset, per_page)
    page = paginator.get_page(request.GET.get(page_name))
    return {
        "data": list(page.object_list),
        "current_page": page.number,
        "last_page": paginator.num_pages,
        "per_page": per_page,
        "total": paginator.count,
        "has_next": page.has_next(),
        "has_previous": page.has_previous(),
    }
