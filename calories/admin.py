from django.contrib import admin
from .models import User, CalorieRecord

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("telegram_id", "username", "joined_at")

@admin.register(CalorieRecord)
class CalorieRecordAdmin(admin.ModelAdmin):
    list_display = ("user", "tdee", "goal", "created_at")
