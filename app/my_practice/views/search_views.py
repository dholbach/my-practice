"""
Global search view for unified search across clients, inquiries, and invoices.
"""

from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from ..models import Client, ClientInquiry, Invoice


def _parse_query_prefix(query: str) -> tuple[str, bool, bool]:
    """Split an optional "c:"/"client:"/"i:"/"invoice:"/"in:" prefix off *query*.

    Returns (query_without_prefix, search_clients, search_invoices).
    """
    if query.startswith("c:") or query.startswith("client:"):
        return query.split(":", 1)[1].strip(), True, False
    if query.startswith("i:") or query.startswith("invoice:") or query.startswith("in:"):
        return query.split(":", 1)[1].strip(), False, True
    return query, True, True


def _client_priority(client, qlo: str) -> tuple:
    # 0: active + code match, 1: active, 2: inactive
    is_code_match = qlo in client.client_code.lower()
    if client.active and is_code_match:
        return (0, -float(client._rank))
    if client.active:
        return (1, -float(client._rank))
    return (2, -float(client._rank))


def _search_clients_and_inquiries(request, query: str) -> list[dict]:
    """Clients + open inquiries (practice-filtered), merged and priority-sorted:
    active clients first, then open inquiries, then inactive clients."""
    name_vector = SearchVector("full_name", config="german")
    name_q = SearchQuery(query, config="german", search_type="plain")
    # Match with the full-text operator (vector @@ query), not `rank > 0`:
    # ts_rank returns 0.0 only for a single-lexeme query that misses. Any
    # multi-lexeme query that misses — two words, or anything Postgres splits on
    # a hyphen, e.g. "kk-9" -> 'kk' & '-9' — scores 1e-20, which is > 0, so the
    # rank test matched every row in the table. SearchRank stays, for ordering.

    clients = (
        Client.objects.for_current_practice(request)
        .alias(_search=name_vector)
        .annotate(_rank=SearchRank(name_vector, name_q))
        .filter(Q(_search=name_q) | Q(client_code__icontains=query) | Q(email__icontains=query))
        .only("id", "client_code", "full_name", "active")
        .order_by("-_rank", "client_code")[:8]
    )

    inq_name_vector = SearchVector("full_name", config="german")
    inq_name_q = SearchQuery(query, config="german", search_type="plain")
    inquiries = (
        ClientInquiry.objects.for_current_practice(request)
        .open()
        .alias(_search=inq_name_vector)
        .annotate(_rank=SearchRank(inq_name_vector, inq_name_q))
        .filter(Q(_search=inq_name_q) | Q(full_name__icontains=query))
        .only("id", "full_name", "status")
        .order_by("-_rank", "full_name")[:8]
    )

    qlo = query.lower()
    client_items = sorted(
        [
            {
                "type": "client",
                "_priority": _client_priority(c, qlo),
                "id": c.id,
                "code": c.client_code,
                "name": c.full_name,
                "url": f"/clients/{c.id}/detail/",
                "label": f"👤 {c.client_code} — {c.full_name}",
            }
            for c in clients
        ],
        key=lambda x: x["_priority"],
    )

    # Open inquiries appear after active clients
    inquiry_items = [
        {
            "type": "inquiry",
            "_priority": (3, -float(inq._rank)),
            "id": inq.id,
            "name": inq.full_name,
            "status": inq.status,
            "url": f"/inquiries/{inq.id}/edit/",
            "label": f"📬 {inq.full_name} ({inq.get_status_display()})",
        }
        for inq in inquiries
    ]

    # Merge: all active clients first, then open inquiries, then inactive clients
    active_clients = [x for x in client_items if x["_priority"][0] < 2]
    inactive_clients = [x for x in client_items if x["_priority"][0] == 2]
    merged = (active_clients + inquiry_items + inactive_clients)[:8]

    # Strip internal sort key before returning
    for item in merged:
        del item["_priority"]
    return merged


def _search_invoices(request, query: str) -> list[dict]:
    """Invoices (practice-filtered) matching invoice number, client code, or client name."""
    inv_name_vector = SearchVector("client__full_name", config="german")
    inv_name_q = SearchQuery(query, config="german", search_type="plain")
    invoices = (
        Invoice.objects.for_current_practice(request)
        .alias(_search=inv_name_vector)
        .annotate(_rank=SearchRank(inv_name_vector, inv_name_q))
        .filter(
            Q(invoice_number__icontains=query)
            | Q(client__client_code__icontains=query)
            | Q(_search=inv_name_q)
        )
        .select_related("client")
        .order_by("-_rank", "-invoice_date")[:5]
    )

    return [
        {
            "type": "invoice",
            "id": invoice.id,
            "invoice_number": invoice.invoice_number,
            "client_code": invoice.client.client_code,
            "client_name": invoice.client.full_name,
            "date": invoice.invoice_date.strftime("%d.%m.%Y"),
            "url": f"/invoices/{invoice.id}/",
            "label": f"📄 {invoice.invoice_number} - {invoice.client.client_code} ({invoice.invoice_date.strftime('%d.%m.%Y')})",
        }
        for invoice in invoices
    ]


@require_http_methods(["GET"])
def global_search(request):
    """
    Global search endpoint supporting prefix-based filtering.

    Query formats:
    - "c:XX" or "client:XX" -> clients + open inquiries (active/direct matches first)
    - "i:2024" or "invoice:2024" -> search only invoices
    - "XX" -> search clients, inquiries, and invoices

    Returns JSON with results sorted by relevance priority.
    """
    query = request.GET.get("q", "").strip()
    if not query:
        return JsonResponse({"results": []})

    query, search_clients, search_invoices = _parse_query_prefix(query)
    if not query:
        return JsonResponse({"results": []})

    results: list[dict] = []
    if search_clients:
        results.extend(_search_clients_and_inquiries(request, query))
    if search_invoices:
        results.extend(_search_invoices(request, query))

    return JsonResponse({"results": results})
