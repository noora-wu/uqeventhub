from django.db import migrations
from django.utils import timezone


def seed_mockup_events(apps, schema_editor):
    AppUser = apps.get_model("uqeventapp", "AppUser")
    Subscriber = apps.get_model("uqeventapp", "Subscriber")
    Category = apps.get_model("uqeventapp", "Category")
    Event = apps.get_model("uqeventapp", "Event")
    EventSession = apps.get_model("uqeventapp", "EventSession")

    user = AppUser.objects.filter(is_superuser=True).first() or AppUser.objects.first()
    if not user:
        user = AppUser.objects.create(
            email="seed@uqeventhub.test",
            username="seed_user",
            password_hash="seed-hash",
            is_active=True,
            is_superuser=False,
        )

    subscriber, _ = Subscriber.objects.get_or_create(
        slug="uq-union",
        defaults={
            "name": "UQ Union",
            "status": "active",
            "contact_email": "contact@uqu.com.au",
        },
    )

    categories = {
        "social": "Social",
        "career": "Career",
        "sport": "Sport",
        "academic": "Academic",
    }
    category_objs = {}
    for slug, name in categories.items():
        category_objs[slug], _ = Category.objects.get_or_create(slug=slug, defaults={"name": name})

    base = timezone.now().replace(minute=0, second=0, microsecond=0)
    samples = [
        {
            "title": "Market Day 2026",
            "tagline": "The biggest day on campus with clubs, societies, and freebies.",
            "category": "social",
            "campus": "St Lucia",
            "venue_display": "Great Court",
            "cost_badge": "free",
            "cost_detail": "Free entry",
            "hero": "https://picsum.photos/seed/marketday/1200/500",
            "days": 3,
            "hours": 10,
        },
        {
            "title": "Careers & Internships Expo 2026",
            "tagline": "Meet employers and graduate programs with CV drop-in support.",
            "category": "career",
            "campus": "St Lucia",
            "venue_display": "UQ Brisbane City",
            "cost_badge": "from",
            "cost_detail": "From $15 student",
            "hero": "https://picsum.photos/seed/careerexpo/1200/500",
            "days": 7,
            "hours": 9,
        },
        {
            "title": "Global Minds Cultural Night",
            "tagline": "Food stalls, performances, and DJ sets for the student community.",
            "category": "social",
            "campus": "St Lucia",
            "venue_display": "Great Court",
            "cost_badge": "free",
            "cost_detail": "Free",
            "hero": "https://picsum.photos/seed/culturalnight/1200/500",
            "days": 10,
            "hours": 18,
        },
        {
            "title": "Rowing Regatta Open Day",
            "tagline": "Try an erg challenge and meet the UQ Boat Club squad.",
            "category": "sport",
            "campus": "St Lucia",
            "venue_display": "St Lucia Boat Club",
            "cost_badge": "free",
            "cost_detail": "Free",
            "hero": "https://picsum.photos/seed/rowingopen/1200/500",
            "days": 14,
            "hours": 8,
        },
        {
            "title": "Public Lecture: Climate Futures",
            "tagline": "Leading researchers discuss adaptation and resilience.",
            "category": "academic",
            "campus": "Online",
            "venue_display": "Online",
            "cost_badge": "free",
            "cost_detail": "Free livestream",
            "hero": "https://picsum.photos/seed/climatelecture/1200/500",
            "days": 18,
            "hours": 17,
            "is_online": True,
            "online_url": "https://example.com/livestream",
        },
    ]

    for item in samples:
        start_at = base + timezone.timedelta(days=item["days"], hours=item["hours"])
        end_at = start_at + timezone.timedelta(hours=3)
        event, _ = Event.objects.get_or_create(
            title=item["title"],
            subscriber=subscriber,
            defaults={
                "created_by": user,
                "category": category_objs[item["category"]],
                "description": item["tagline"],
                "tagline": item["tagline"],
                "cost_badge": item["cost_badge"],
                "cost_detail": item["cost_detail"],
                "hero_image_url": item["hero"],
                "start_at": start_at,
                "end_at": end_at,
                "time_summary": f"{start_at:%I:%M%p} - {end_at:%I:%M%p}",
                "venue_display": item["venue_display"],
                "campus": item["campus"],
                "is_online": item.get("is_online", False),
                "online_url": item.get("online_url", ""),
                "maps_url": "",
                "sessions_intro": "Select sessions and register.",
                "highlight_bullets": "",
                "capacity": 300,
                "visibility": "public",
                "status": "published",
            },
        )
        EventSession.objects.get_or_create(
            event=event,
            title="General admission",
            defaults={
                "abstract": "Main session",
                "start_at": start_at,
                "end_at": end_at,
                "time_label": f"{start_at:%I:%M%p} - {end_at:%I:%M%p}",
                "location_label": item["venue_display"],
                "capacity": 300,
                "registration_kind": "limited",
                "order_index": 1,
            },
        )


def unseed_mockup_events(apps, schema_editor):
    Event = apps.get_model("uqeventapp", "Event")
    titles = [
        "Market Day 2026",
        "Careers & Internships Expo 2026",
        "Global Minds Cultural Night",
        "Rowing Regatta Open Day",
        "Public Lecture: Climate Futures",
    ]
    Event.objects.filter(title__in=titles).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("uqeventapp", "0002_seed_sample_data"),
    ]

    operations = [
        migrations.RunPython(seed_mockup_events, unseed_mockup_events),
    ]
