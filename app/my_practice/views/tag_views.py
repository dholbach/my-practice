"""
Tag management views for clients.
"""

from django.contrib import messages
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views.decorators.http import require_http_methods, require_POST
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from ..models import Client, ClientTag
from ..utils import sort_tags_by_category


class TagListView(ListView):
    """List all available tags"""

    model = ClientTag
    template_name = "my_practice/tag_list.html"
    context_object_name = "tags"
    paginate_by = 50

    def get_queryset(self):
        return ClientTag.objects.annotate(client_count=Count("clients")).order_by("name")


class TagCreateView(CreateView):
    """Create a new tag"""

    model = ClientTag
    template_name = "my_practice/tag_form.html"
    fields = ["name", "color", "description"]
    success_url = reverse_lazy("tag_list")

    def form_valid(self, form):
        messages.success(self.request, f"Tag '{form.instance.name}' erfolgreich erstellt!")
        return super().form_valid(form)


class TagUpdateView(UpdateView):
    """Edit an existing tag"""

    model = ClientTag
    template_name = "my_practice/tag_form.html"
    fields = ["name", "color", "description"]
    success_url = reverse_lazy("tag_list")

    def form_valid(self, form):
        messages.success(self.request, f"Tag '{form.instance.name}' erfolgreich aktualisiert!")
        return super().form_valid(form)


class TagDeleteView(DeleteView):
    """Delete a tag"""

    model = ClientTag
    template_name = "my_practice/tag_confirm_delete.html"
    success_url = reverse_lazy("tag_list")

    def form_valid(self, form):
        tag_name = self.object.name
        messages.success(self.request, f"Tag '{tag_name}' erfolgreich gelöscht!")
        return super().form_valid(form)


@require_POST
def client_add_tag(request, client_id):
    """Add a tag to a client (AJAX endpoint)"""
    client = get_object_or_404(Client, pk=client_id)
    tag_id = request.POST.get("tag_id")

    if not tag_id:
        return JsonResponse({"error": "Tag ID required"}, status=400)

    tag = get_object_or_404(ClientTag, pk=tag_id)
    client.tags.add(tag)

    return JsonResponse(
        {
            "success": True,
            "message": f"Tag '{tag.name}' hinzugefügt",
            "tag": {"id": tag.id, "name": tag.name, "color": tag.color},
        }
    )


@require_POST
def client_remove_tag(request, client_id, tag_id):
    """Remove a tag from a client (AJAX endpoint)"""
    client = get_object_or_404(Client, pk=client_id)
    tag = get_object_or_404(ClientTag, pk=tag_id)

    client.tags.remove(tag)

    return JsonResponse(
        {
            "success": True,
            "message": f"Tag '{tag.name}' entfernt",
        }
    )


@require_http_methods(["GET"])
def get_available_tags(request):
    """Get all available tags (AJAX endpoint for autocomplete/dropdown)"""
    client_id = request.GET.get("client_id")

    tags = ClientTag.objects.filter(is_system=False)

    # Optionally exclude tags already assigned to this client (practice-filtered)
    if client_id:
        client = get_object_or_404(Client.objects.for_current_practice(request), pk=client_id)
        tags = tags.exclude(clients=client)

    # Sort by category priority (attention → general → exit), then alphabetically
    sorted_tags = sort_tags_by_category(tags)

    tags_data = [{"id": tag.id, "name": tag.name, "color": tag.color} for tag in sorted_tags]

    return JsonResponse({"tags": tags_data})
