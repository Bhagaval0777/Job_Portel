from django.contrib import admin
from .models import SubscriptionPlan, UserSubscription, RecruiterUsage

admin.site.register(RecruiterUsage)
@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):

    list_display = (
        'id',
        'name',
        'price',
        'duration',
        'user_type'
    )

    search_fields = ('name',)

    list_filter = ('user_type',)


@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):

    list_display = (
        'id',
        'user',
        'plan',
        'start_date',
        'end_date'
    )