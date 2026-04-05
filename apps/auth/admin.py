from django.contrib import admin
from .models import UserProfile, WatchlistItem, SignalLog, PaperTrade, PriceAlert


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("email", "name", "is_master", "login_count", "last_login", "created_at")
    list_filter = ("is_master", "provider", "created_at")
    search_fields = ("email", "name", "uid")
    readonly_fields = ("uid", "created_at", "last_login", "login_count")


@admin.register(WatchlistItem)
class WatchlistItemAdmin(admin.ModelAdmin):
    list_display = ("user", "symbol", "label", "added_at")
    list_filter = ("added_at",)
    search_fields = ("symbol", "user__email")


@admin.register(PaperTrade)
class PaperTradeAdmin(admin.ModelAdmin):
    list_display = ("symbol", "direction", "status", "entry", "exit_price", "user", "opened_at")
    list_filter = ("status", "direction", "opened_at")
    search_fields = ("symbol", "user__email")


@admin.register(PriceAlert)
class PriceAlertAdmin(admin.ModelAdmin):
    list_display = ("symbol", "direction", "trigger_price", "active", "triggered_at", "user", "created_at")
    list_filter = ("active", "direction", "created_at")
    search_fields = ("symbol", "user__email")


@admin.register(SignalLog)
class SignalLogAdmin(admin.ModelAdmin):
    list_display = ("symbol", "direction", "action", "confidence", "entry", "user", "created_at")
    list_filter = ("direction", "action", "created_at")
    search_fields = ("symbol", "user__email")
    date_hierarchy = "created_at"
