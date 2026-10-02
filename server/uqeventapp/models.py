from django.db import models

class AppUser(models.Model):
    email = models.EmailField(unique=True)
    username = models.CharField(max_length=150, unique=True)
    password_hash = models.CharField(max_length=255, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_superuser = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "users"

    def __str__(self):
        return self.username


class Subscriber(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"

    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    contact_email = models.EmailField()
    tagline = models.TextField(blank=True)
    description = models.TextField(blank=True)
    website_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    suspended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "subscribers"

    def __str__(self):
        return self.name


class SubscriberOfficialLink(models.Model):
    subscriber = models.ForeignKey(Subscriber, on_delete=models.CASCADE, related_name="official_links")
    label = models.CharField(max_length=120)
    url = models.URLField()
    sort_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "subscriber_official_links"


class SubscriberStaff(models.Model):
    class Role(models.TextChoices):
        EDITOR = "editor", "Editor"
        ADMIN = "admin", "Admin"

    user = models.ForeignKey(AppUser, on_delete=models.CASCADE, related_name="subscriber_roles")
    subscriber = models.ForeignKey(Subscriber, on_delete=models.CASCADE, related_name="staff_memberships")
    role = models.CharField(max_length=20, choices=Role.choices)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "subscriber_staff"


class Category(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=120, unique=True)

    class Meta:
        db_table = "categories"

    def __str__(self):
        return self.name


class Venue(models.Model):
    name = models.CharField(max_length=255)
    campus = models.CharField(max_length=100, blank=True)
    building_code = models.CharField(max_length=50, blank=True)
    address_line = models.CharField(max_length=255, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "venues"

    def __str__(self):
        return self.name


class Event(models.Model):
    class CostBadge(models.TextChoices):
        FREE = "free", "Free"
        PAID = "paid", "Paid"
        FROM = "from", "From"

    class Visibility(models.TextChoices):
        PUBLIC = "public", "Public"
        UQ_ONLY = "uq_only", "UQ Only"
        SUBSCRIBER_ONLY = "subscriber_only", "Subscriber Only"
        INVITE_ONLY = "invite_only", "Invite Only"

    class Status(models.TextChoices):
        PUBLISHED = "published", "Published"
        CANCELLED = "cancelled", "Cancelled"
        ARCHIVED = "archived", "Archived"
        DRAFT = "draft", "Draft"

    subscriber = models.ForeignKey(Subscriber, on_delete=models.CASCADE, related_name="events")
    created_by = models.ForeignKey(AppUser, on_delete=models.SET_NULL, null=True, related_name="created_events")
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="events")
    title = models.CharField(max_length=255)
    description = models.TextField()
    tagline = models.CharField(max_length=255, blank=True)
    cost_badge = models.CharField(max_length=20, choices=CostBadge.choices, blank=True)
    cost_detail = models.CharField(max_length=120, blank=True)
    hero_image_url = models.URLField(blank=True)
    start_at = models.DateTimeField(null=True, blank=True)
    end_at = models.DateTimeField(null=True, blank=True)
    time_summary = models.CharField(max_length=255, blank=True)
    venue = models.ForeignKey(Venue, on_delete=models.SET_NULL, null=True, blank=True, related_name="events")
    venue_display = models.CharField(max_length=255, blank=True)
    campus = models.CharField(max_length=100, blank=True)
    is_online = models.BooleanField(default=False)
    online_url = models.URLField(blank=True)
    maps_url = models.URLField(blank=True)
    sessions_intro = models.TextField(blank=True)
    highlight_bullets = models.TextField(blank=True)
    capacity = models.IntegerField(null=True, blank=True)
    visibility = models.CharField(max_length=30, choices=Visibility.choices, default=Visibility.PUBLIC)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PUBLISHED)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "events"

    def __str__(self):
        return self.title


class EventSession(models.Model):
    class RegistrationKind(models.TextChoices):
        NONE = "none", "None"
        TICKETED = "ticketed", "Ticketed"
        LIMITED = "limited", "Limited"

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="sessions")
    title = models.CharField(max_length=255)
    abstract = models.TextField(blank=True)
    start_at = models.DateTimeField(null=True, blank=True)
    end_at = models.DateTimeField(null=True, blank=True)
    time_label = models.CharField(max_length=120, blank=True)
    location_label = models.CharField(max_length=255, blank=True)
    capacity = models.IntegerField(null=True, blank=True)
    registration_kind = models.CharField(max_length=20, choices=RegistrationKind.choices, default=RegistrationKind.NONE)
    order_index = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "event_sessions"

    def __str__(self):
        return f"{self.event.title} - {self.title}"


class Registration(models.Model):
    class Status(models.TextChoices):
        CONFIRMED = "confirmed", "Confirmed"
        CANCELLED = "cancelled", "Cancelled"

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="registrations")
    user = models.ForeignKey(AppUser, on_delete=models.SET_NULL, null=True, blank=True, related_name="registrations")
    guest_email = models.EmailField(blank=True)
    guest_name = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.CONFIRMED)
    checked_in_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "registrations"


class RegistrationSession(models.Model):
    registration = models.ForeignKey(Registration, on_delete=models.CASCADE, related_name="registration_sessions")
    event_session = models.ForeignKey(EventSession, on_delete=models.CASCADE, related_name="session_registrations")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "registration_sessions"
        unique_together = ("registration", "event_session")