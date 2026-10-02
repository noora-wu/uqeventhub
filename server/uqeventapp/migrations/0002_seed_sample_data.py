from django.db import migrations
from django.utils import timezone


def seed_sample_data(apps, schema_editor):
    AppUser = apps.get_model("uqeventapp", "AppUser")
    Subscriber = apps.get_model("uqeventapp", "Subscriber")
    SubscriberOfficialLink = apps.get_model("uqeventapp", "SubscriberOfficialLink")
    SubscriberStaff = apps.get_model("uqeventapp", "SubscriberStaff")
    Category = apps.get_model("uqeventapp", "Category")
    Venue = apps.get_model("uqeventapp", "Venue")
    Event = apps.get_model("uqeventapp", "Event")
    EventSession = apps.get_model("uqeventapp", "EventSession")
    Registration = apps.get_model("uqeventapp", "Registration")
    RegistrationSession = apps.get_model("uqeventapp", "RegistrationSession")

    user, _ = AppUser.objects.get_or_create(
        email="admin@uqeventhub.test",
        defaults={
            "username": "admin_app",
            "password_hash": "demo-hash",
            "is_active": True,
            "is_superuser": True,
        },
    )

    subscriber, _ = Subscriber.objects.get_or_create(
        slug="uq-union",
        defaults={
            "name": "UQ Union",
            "status": "active",
            "contact_email": "contact@uqu.com.au",
            "tagline": "Student life at UQ",
            "description": "Sample subscriber profile for development and demos.",
            "website_url": "https://uqu.com.au",
        },
    )

    SubscriberOfficialLink.objects.get_or_create(
        subscriber=subscriber,
        label="Website",
        defaults={"url": "https://uqu.com.au", "sort_order": 0},
    )
    SubscriberOfficialLink.objects.get_or_create(
        subscriber=subscriber,
        label="Instagram",
        defaults={"url": "https://instagram.com/uqunion", "sort_order": 1},
    )

    SubscriberStaff.objects.get_or_create(
        user=user,
        subscriber=subscriber,
        defaults={"role": "admin", "is_active": True},
    )

    category, _ = Category.objects.get_or_create(name="Careers", defaults={"slug": "careers"})
    venue, _ = Venue.objects.get_or_create(
        name="Great Court",
        defaults={
            "campus": "St Lucia",
            "building_code": "UQ-GC",
            "address_line": "The University of Queensland, St Lucia QLD",
            "latitude": -27.497500,
            "longitude": 153.013700,
        },
    )

    now = timezone.now()
    event_start = now + timezone.timedelta(days=7)
    event_end = event_start + timezone.timedelta(hours=6)

    event, _ = Event.objects.get_or_create(
        subscriber=subscriber,
        title="Careers & Internships Expo 2026",
        defaults={
            "created_by": user,
            "category": category,
            "description": "Meet employers, discover internships, and book CV review sessions.",
            "tagline": "Meet top employers on campus",
            "cost_badge": "from",
            "cost_detail": "From $15 student",
            "hero_image_url": "https://picsum.photos/seed/careerexpo/1200/500",
            "start_at": event_start,
            "end_at": event_end,
            "time_summary": "Main fair 9:00am-3:00pm AEST",
            "venue": venue,
            "venue_display": "Great Court",
            "campus": "St Lucia",
            "is_online": False,
            "maps_url": "https://maps.google.com/?q=UQ+Great+Court",
            "sessions_intro": "Choose one or more sessions below.",
            "highlight_bullets": "Employer booths\nCV drop-in studio\nInterview practice",
            "capacity": 500,
            "visibility": "public",
            "status": "published",
        },
    )

    session_1, _ = EventSession.objects.get_or_create(
        event=event,
        title="Morning session",
        defaults={
            "abstract": "Employer booths and networking for morning attendees.",
            "start_at": event_start,
            "end_at": event_start + timezone.timedelta(hours=3),
            "time_label": "9:00am-12:00pm",
            "location_label": "Great Court",
            "capacity": 250,
            "registration_kind": "ticketed",
            "order_index": 1,
        },
    )
    session_2, _ = EventSession.objects.get_or_create(
        event=event,
        title="Afternoon session",
        defaults={
            "abstract": "CV clinics and speed interview demos.",
            "start_at": event_start + timezone.timedelta(hours=3),
            "end_at": event_end,
            "time_label": "12:00pm-3:00pm",
            "location_label": "Great Court",
            "capacity": 250,
            "registration_kind": "limited",
            "order_index": 2,
        },
    )

    registration, _ = Registration.objects.get_or_create(
        event=event,
        user=user,
        defaults={"status": "confirmed"},
    )
    RegistrationSession.objects.get_or_create(registration=registration, event_session=session_1)
    RegistrationSession.objects.get_or_create(registration=registration, event_session=session_2)


def unseed_sample_data(apps, schema_editor):
    AppUser = apps.get_model("uqeventapp", "AppUser")
    Event = apps.get_model("uqeventapp", "Event")
    Subscriber = apps.get_model("uqeventapp", "Subscriber")
    Category = apps.get_model("uqeventapp", "Category")
    Venue = apps.get_model("uqeventapp", "Venue")

    Event.objects.filter(title="Careers & Internships Expo 2026").delete()
    Subscriber.objects.filter(slug="uq-union").delete()
    Category.objects.filter(slug="careers").delete()
    Venue.objects.filter(name="Great Court").delete()
    AppUser.objects.filter(email="admin@uqeventhub.test").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("uqeventapp", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_sample_data, unseed_sample_data),
    ]
