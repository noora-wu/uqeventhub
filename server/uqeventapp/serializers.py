from rest_framework import serializers

from .models import Event, EventSession, Registration, RegistrationSession, Subscriber, SubscriberStaff


class SubscriberSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscriber
        fields = "__all__"


class SubscriberStaffSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)
    subscriber_name = serializers.CharField(source="subscriber.name", read_only=True)

    class Meta:
        model = SubscriberStaff
        fields = "__all__"


class EventSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventSession
        fields = "__all__"


class EventSerializer(serializers.ModelSerializer):
    subscriber_name = serializers.CharField(source="subscriber.name", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)
    sessions = EventSessionSerializer(many=True, read_only=True)

    class Meta:
        model = Event
        fields = "__all__"


class RegistrationSessionSerializer(serializers.ModelSerializer):
    event_session_title = serializers.CharField(source="event_session.title", read_only=True)

    class Meta:
        model = RegistrationSession
        fields = "__all__"


class RegistrationSerializer(serializers.ModelSerializer):
    event_title = serializers.CharField(source="event.title", read_only=True)
    user_email = serializers.EmailField(source="user.email", read_only=True)
    registration_sessions = RegistrationSessionSerializer(many=True, read_only=True)

    class Meta:
        model = Registration
        fields = "__all__"
