from rest_framework import serializers

from .models import (
    SubscriptionPlan,
    UserSubscription,
    RecruiterUsage
)

class SubscriptionPlanSerializer(
    serializers.ModelSerializer
):

    class Meta:

        model = SubscriptionPlan

        fields = '__all__'

class UserSubscriptionSerializer(
    serializers.ModelSerializer
):

    class Meta:

        model = UserSubscription

        fields = '__all__'

class RecruiterUsageSerializer(
    serializers.ModelSerializer
):

    class Meta:

        model = RecruiterUsage

        fields = '__all__'

