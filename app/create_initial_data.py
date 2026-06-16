"""
Create initial data: Service Types and Test Client
"""

from my_practice.models import Client, ServiceType

# Service Types
service_types = [
    {"code": "therapy_60", "name": "60-Min Therapy Session", "default_duration": 60},
    {"code": "therapy_90", "name": "90-Min Therapy Session", "default_duration": 90},
    {
        "code": "initial_consultation",
        "name": "Initial Consultation",
        "default_duration": 60,
    },
    {"code": "cancellation", "name": "Cancellation Fee", "default_duration": 0},
]

for st_data in service_types:
    st, created = ServiceType.objects.get_or_create(
        code=st_data["code"],
        defaults={
            "name": st_data["name"],
            "default_duration": st_data["default_duration"],
        },
    )
    if created:
        print(f"✓ Created: {st.name}")
    else:
        print(f"- Already exists: {st.name}")

# Test Client
client, created = Client.objects.get_or_create(
    client_code="DE",
    defaults={
        "full_name": "Test Client",
        "email": "test@example.com",
        "language": "de",
        "hourly_rate_60": 90.00,
        "hourly_rate_90": 130.00,
        "active": True,
    },
)
if created:
    print(f"\n✓ Created test client: {client.client_code} - {client.full_name}")
else:
    print(f"\n- Test client already exists: {client.client_code} - {client.full_name}")

print("\n✅ Initial data setup complete!")
