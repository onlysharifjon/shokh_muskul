from django.contrib import admin
from .models import User, CalorieRecord


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("id", "username", "telegram_id", "joined_at")
    search_fields = ("username", "telegram_id")
    ordering = ("-joined_at",)


@admin.register(CalorieRecord)
class CalorieRecordAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "goal", "tdee", "created_at")
    search_fields = ("user__username", "goal")
    ordering = ("-created_at",)
