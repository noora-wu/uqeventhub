from django.db import migrations
from django.utils import timezone


def backfill_minimum_demo_data(apps, schema_editor):
    AppUser = apps.get_model("uqeventapp", "AppUser")
    Subscriber = apps.get_model("uqeventapp", "Subscriber")
    Category = apps.get_model("uqeventapp", "Category")
    Venue = apps.get_model("uqeventapp", "Venue")
    Event = apps.get_model("uqeventapp", "Event")
    EventSession = apps.get_model("uqeventapp", "EventSession")
    SubscriberStaff = apps.get_model("uqeventapp", "SubscriberStaff")

    admin_user, _ = AppUser.objects.get_or_create(
        email="admin@uqeventhub.test",
        defaults={
            "username": "admin_app",
            "password_hash": "demo-hash",
            "is_active": True,
            "is_superuser": True,
        },
    )

    uq_union, _ = Subscriber.objects.get_or_create(
        slug="uq-union",
        defaults={
            "name": "UQ Union",
            "status": "active",
            "contact_email": "contact@uqu.com.au",
            "tagline": "Student life at UQ",
            "description": "Sample subscriber profile for development and demos.",
            "website_url": "https://www.uqu.com.au/",
        },
    )

    SubscriberStaff.objects.get_or_create(
        user=admin_user,
        subscriber=uq_union,
        defaults={"role": "admin", "is_active": True},
    )

    general_category, _ = Category.objects.get_or_create(
        slug="general",
        defaults={"name": "General"},
    )
    social_category, _ = Category.objects.get_or_create(
        slug="social",
        defaults={"name": "Social"},
    )
    careers_category, _ = Category.objects.get_or_create(
        slug="career",
        defaults={"name": "Career"},
    )

    great_court, _ = Venue.objects.get_or_create(
        name="Great Court",
        defaults={
            "campus": "St Lucia",
            "building_code": "UQ-GC",
            "address_line": "The University of Queensland, St Lucia QLD",
        },
    )

    # Ensure existing records have non-null relationships used by templates.
    Event.objects.filter(subscriber__isnull=True).update(subscriber=uq_union)
    Event.objects.filter(category__isnull=True).update(category=general_category)

    now = timezone.now().replace(minute=0, second=0, microsecond=0)
    market_start = now + timezone.timedelta(days=5, hours=10)
    careers_start = now + timezone.timedelta(days=7, hours=10)

    market_event, _ = Event.objects.get_or_create(
        title="Market Day 2026",
        subscriber=uq_union,
        defaults={
            "created_by": admin_user,
            "category": social_category,
            "description": "The biggest day on campus with clubs, societies, and freebies.",
            "tagline": "The biggest day on campus with clubs, societies, and freebies.",
            "cost_badge": "free",
            "cost_detail": "Free entry",
            "hero_image_url": "https://picsum.photos/seed/marketday/1200/500",
            "start_at": market_start,
            "end_at": market_start + timezone.timedelta(hours=4),
            "time_summary": "10:00am - 2:00pm AEST",
            "venue": great_court,
            "venue_display": "Great Court",
            "campus": "St Lucia",
            "maps_url": "https://maps.google.com/?q=UQ+Great+Court",
            "capacity": 600,
            "visibility": "public",
            "status": "published",
        },
    )

    careers_event, _ = Event.objects.get_or_create(
        title="Careers & Internships Expo 2026",
        subscriber=uq_union,
        defaults={
            "created_by": admin_user,
            "category": careers_category,
            "description": "Meet employers and graduate programs with CV drop-in support.",
            "tagline": "Meet employers and graduate programs with CV drop-in support.",
            "cost_badge": "from",
            "cost_detail": "From $15 student",
            "hero_image_url": "https://picsum.photos/seed/careerexpo/1200/500",
            "start_at": careers_start,
            "end_at": careers_start + timezone.timedelta(hours=6),
            "time_summary": "10:00am - 4:00pm AEST",
            "venue_display": "UQ Brisbane City",
            "campus": "Brisbane City",
            "capacity": 800,
            "visibility": "public",
            "status": "published",
        },
    )

    EventSession.objects.get_or_create(
        event=market_event,
        title="General admission",
        defaults={
            "abstract": "Main session",
            "start_at": market_start,
            "end_at": market_start + timezone.timedelta(hours=4),
            "time_label": "10:00am - 2:00pm",
            "location_label": "Great Court",
            "capacity": 600,
            "registration_kind": "limited",
            "order_index": 1,
        },
    )
    EventSession.objects.get_or_create(
        event=careers_event,
        title="General admission",
        defaults={
            "abstract": "Main session",
            "start_at": careers_start,
            "end_at": careers_start + timezone.timedelta(hours=6),
            "time_label": "10:00am - 4:00pm",
            "location_label": "UQ Brisbane City",
            "capacity": 800,
            "registration_kind": "limited",
            "order_index": 1,
        },
    )


def reverse_backfill_minimum_demo_data(apps, schema_editor):
    # Keep data on rollback to avoid breaking environments.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("uqeventapp", "0003_seed_mockup_events"),
    ]

    operations = [
        migrations.RunPython(backfill_minimum_demo_data, reverse_backfill_minimum_demo_data),
    ]

