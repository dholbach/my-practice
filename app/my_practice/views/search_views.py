"""
Global search view for unified search across clients, inquiries, and invoices.
"""

from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from ..models import Client, ClientInquiry, Invoice


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

    # Parse prefix
    search_clients = True
    search_invoices = True

    if query.startswith("c:") or query.startswith("client:"):
        search_invoices = False
        query = query.split(":", 1)[1].strip()
    elif query.startswith("i:") or query.startswith("invoice:") or query.startswith("in:"):
        search_clients = False
        query = query.split(":", 1)[1].strip()

    if not query:
        return JsonResponse({"results": []})

    results: list[dict] = []

    # Search clients + open inquiries (practice-filtered), merged and priority-sorted
    if search_clients:
        name_vector = SearchVector("full_name", config="german")
        name_q = SearchQuery(query, config="german", search_type="plain")

        clients = (
            Client.objects.for_current_practice(request)
            .annotate(_rank=SearchRank(name_vector, name_q))
            .filter(Q(_rank__gt=0) | Q(client_code__icontains=query) | Q(email__icontains=query))
            .only("id", "client_code", "full_name", "active")
            .order_by("-_rank", "client_code")[:8]
        )

        inq_name_vector = SearchVector("full_name", config="german")
        inq_name_q = SearchQuery(query, config="german", search_type="plain")
        inquiries = (
            ClientInquiry.objects.for_current_practice(request)
            .open()
            .annotate(_rank=SearchRank(inq_name_vector, inq_name_q))
            .filter(Q(_rank__gt=0) | Q(full_name__icontains=query))
            .only("id", "full_name", "status")
            .order_by("-_rank", "full_name")[:8]
        )

        qlo = query.lower()

        def _client_priority(c) -> tuple:
            # 0: active + code match, 1: active, 2: inactive
            is_code_match = qlo in c.client_code.lower()
            if c.active and is_code_match:
                return (0, -float(c._rank))
            if c.active:
                return (1, -float(c._rank))
            return (2, -float(c._rank))

        client_items = sorted(
            [
                {
                    "type": "client",
                    "_priority": _client_priority(c),
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

        results.extend(merged)

    # Search invoices (practice-filtered)
    if search_invoices:
        inv_name_vector = SearchVector("client__full_name", config="german")
        inv_name_q = SearchQuery(query, config="german", search_type="plain")
        invoices = (
            Invoice.objects.for_current_practice(request)
            .annotate(_rank=SearchRank(inv_name_vector, inv_name_q))
            .filter(
                Q(invoice_number__icontains=query)
                | Q(client__client_code__icontains=query)
                | Q(_rank__gt=0)
            )
            .select_related("client")
            .order_by("-_rank", "-invoice_date")[:5]
        )

        results.extend(
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
        )

    return JsonResponse({"results": results})
