#!/usr/bin/env python
"""Update short_title for practice"""

from my_practice.models import Practice

p = Practice.objects.get(slug="your-practice-slug")
p.short_title = "Coaching"
p.save()
print(f'✓ Updated {p.name}: short_title="{p.short_title}"')
