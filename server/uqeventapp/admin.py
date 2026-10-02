from django.contrib import admin

from .models import (
    AppUser,
    Category,
    Event,
    EventSession,
    Registration,
    RegistrationSession,
    Subscriber,
    SubscriberOfficialLink,
    SubscriberStaff,
    Venue,
)


@admin.action(description="Activate selected users")
def activate_users(modeladmin, request, queryset):
    updated = queryset.update(is_active=True)
    modeladmin.message_user(request, f"{updated} user(s) activated.")


@admin.action(description="Deactivate selected users")
def deactivate_users(modeladmin, request, queryset):
    updated = queryset.update(is_active=False)
    modeladmin.message_user(request, f"{updated} user(s) deactivated.")


@admin.register(AppUser)
class AppUserAdmin(admin.ModelAdmin):
    list_display = ("username", "email", "is_active", "is_superuser", "created_at")
    list_filter = ("is_active", "is_superuser")
    search_fields = ("username", "email")
    actions = (activate_users, deactivate_users)


class SubscriberOfficialLinkInline(admin.TabularInline):
    model = SubscriberOfficialLink
    extra = 0


class SubscriberStaffInline(admin.TabularInline):
    model = SubscriberStaff
    extra = 0


@admin.register(Subscriber)
class SubscriberAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "status", "contact_email", "created_at")
    list_filter = ("status",)
    search_fields = ("name", "slug", "contact_email", "tagline", "description")
    prepopulated_fields = {"slug": ("name",)}
    inlines = (SubscriberOfficialLinkInline, SubscriberStaffInline)
    actions = ("mark_active", "mark_suspended")

    def has_delete_permission(self, request, obj=None):
        """Subscriptions are archived (suspended), not hard-deleted."""
        return False

    @admin.action(description="Mark selected subscribers as active")
    def mark_active(self, request, queryset):
        updated = queryset.update(status=Subscriber.Status.ACTIVE, suspended_at=None)
        self.message_user(request, f"{updated} subscriber(s) marked active.")

    @admin.action(description="Mark selected subscribers as suspended")
    def mark_suspended(self, request, queryset):
        updated = queryset.update(status=Subscriber.Status.SUSPENDED)
        self.message_user(request, f"{updated} subscriber(s) suspended.")


@admin.register(SubscriberOfficialLink)
class SubscriberOfficialLinkAdmin(admin.ModelAdmin):
    list_display = ("subscriber", "label", "url", "sort_order", "created_at")
    list_filter = ("subscriber",)
    search_fields = ("subscriber__name", "label", "url")
    autocomplete_fields = ("subscriber",)


@admin.register(SubscriberStaff)
class SubscriberStaffAdmin(admin.ModelAdmin):
    list_display = ("user", "subscriber", "role", "is_active", "created_at")
    list_filter = ("role", "is_active", "subscriber")
    search_fields = ("user__username", "user__email", "subscriber__name")
    autocomplete_fields = ("user", "subscriber")
    actions = ("activate_staff", "deactivate_staff")

    @admin.action(description="Activate selected staff memberships")
    def activate_staff(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} staff membership(s) activated.")

    @admin.action(description="Deactivate selected staff memberships")
    def deactivate_staff(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} staff membership(s) deactivated.")


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Venue)
class VenueAdmin(admin.ModelAdmin):
    list_display = ("name", "campus", "building_code", "address_line")
    search_fields = ("name", "campus", "building_code", "address_line")


class EventSessionInline(admin.TabularInline):
    model = EventSession
    extra = 0


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("title", "subscriber", "category", "status", "visibility", "start_at", "venue")
    list_filter = ("status", "visibility", "category", "campus", "is_online")
    search_fields = ("title", "tagline", "description", "subscriber__name", "venue__name")
    autocomplete_fields = ("subscriber", "created_by", "category", "venue")
    date_hierarchy = "start_at"
    inlines = (EventSessionInline,)
    actions = ("mark_published", "mark_draft", "mark_cancelled", "mark_archived")

    @admin.action(description="Mark selected events as published")
    def mark_published(self, request, queryset):
        updated = queryset.update(status=Event.Status.PUBLISHED)
        self.message_user(request, f"{updated} event(s) marked published.")

    @admin.action(description="Mark selected events as draft")
    def mark_draft(self, request, queryset):
        updated = queryset.update(status=Event.Status.DRAFT)
        self.message_user(request, f"{updated} event(s) marked draft.")

    @admin.action(description="Mark selected events as cancelled")
    def mark_cancelled(self, request, queryset):
        updated = queryset.update(status=Event.Status.CANCELLED)
        self.message_user(request, f"{updated} event(s) marked cancelled.")

    @admin.action(description="Mark selected events as archived")
    def mark_archived(self, request, queryset):
        updated = queryset.update(status=Event.Status.ARCHIVED)
        self.message_user(request, f"{updated} event(s) marked archived.")


@admin.register(EventSession)
class EventSessionAdmin(admin.ModelAdmin):
    list_display = ("title", "event", "start_at", "end_at", "registration_kind", "capacity")
    list_filter = ("registration_kind",)
    search_fields = ("title", "abstract", "event__title")
    autocomplete_fields = ("event",)


class RegistrationSessionInline(admin.TabularInline):
    model = RegistrationSession
    extra = 0


@admin.register(Registration)
class RegistrationAdmin(admin.ModelAdmin):
    list_display = ("event", "user", "guest_name", "guest_email", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("event__title", "user__username", "user__email", "guest_name", "guest_email")
    autocomplete_fields = ("event", "user")
    inlines = (RegistrationSessionInline,)
    actions = ("mark_confirmed", "mark_cancelled")

    @admin.action(description="Mark selected registrations as confirmed")
    def mark_confirmed(self, request, queryset):
        updated = queryset.update(status=Registration.Status.CONFIRMED)
        self.message_user(request, f"{updated} registration(s) marked confirmed.")

    @admin.action(description="Mark selected registrations as cancelled")
    def mark_cancelled(self, request, queryset):
        updated = queryset.update(status=Registration.Status.CANCELLED)
        self.message_user(request, f"{updated} registration(s) marked cancelled.")


@admin.register(RegistrationSession)
class RegistrationSessionAdmin(admin.ModelAdmin):
    list_display = ("registration", "event_session", "created_at")
    autocomplete_fields = ("registration", "event_session")
