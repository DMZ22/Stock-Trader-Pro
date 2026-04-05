"""User profile and activity persistence."""
from django.db import models


class UserProfile(models.Model):
    """Profile for Firebase-authenticated users, keyed by uid."""
    uid = models.CharField(max_length=128, primary_key=True)
    email = models.EmailField(max_length=255, db_index=True)
    name = models.CharField(max_length=255, blank=True, default="")
    picture = models.URLField(blank=True, default="")
    provider = models.CharField(max_length=50, blank=True, default="")
    is_master = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(auto_now=True)
    login_count = models.IntegerField(default=0)

    class Meta:
        db_table = "user_profile"

    def __str__(self):
        return f"{self.email} ({'master' if self.is_master else 'user'})"


class WatchlistItem(models.Model):
    """User's saved symbols for quick access."""
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name="watchlist")
    symbol = models.CharField(max_length=32)
    label = models.CharField(max_length=128, blank=True, default="")
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "watchlist_item"
        unique_together = [("user", "symbol")]
        ordering = ["-added_at"]

    def __str__(self):
        return f"{self.user.email}: {self.symbol}"


class PaperTrade(models.Model):
    """Paper-trading position for P&L tracking."""
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    STATUS_CHOICES = [(OPEN, "Open"), (CLOSED, "Closed")]

    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name="trades")
    symbol = models.CharField(max_length=32, db_index=True)
    direction = models.CharField(max_length=10)  # LONG / SHORT
    entry = models.FloatField()
    stop_loss = models.FloatField(null=True, blank=True)
    take_profit = models.FloatField(null=True, blank=True)
    quantity = models.FloatField(default=1.0)
    exit_price = models.FloatField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=OPEN)
    opened_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    notes = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        db_table = "paper_trade"
        ordering = ["-opened_at"]

    @property
    def is_open(self) -> bool:
        return self.status == self.OPEN

    def pnl_abs(self, current_price: float) -> float:
        """Realized P&L if closed, unrealized if open."""
        price = self.exit_price if self.exit_price is not None else current_price
        if self.direction == "LONG":
            return (price - self.entry) * self.quantity
        return (self.entry - price) * self.quantity

    def pnl_pct(self, current_price: float) -> float:
        if not self.entry: return 0.0
        price = self.exit_price if self.exit_price is not None else current_price
        if self.direction == "LONG":
            return (price - self.entry) / self.entry * 100
        return (self.entry - price) / self.entry * 100


class PriceAlert(models.Model):
    """Price alert that fires when a threshold is crossed."""
    ABOVE = "ABOVE"
    BELOW = "BELOW"
    DIR_CHOICES = [(ABOVE, "Above"), (BELOW, "Below")]

    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name="alerts")
    symbol = models.CharField(max_length=32, db_index=True)
    trigger_price = models.FloatField()
    direction = models.CharField(max_length=10, choices=DIR_CHOICES)
    message = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    triggered_at = models.DateTimeField(null=True, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        db_table = "price_alert"
        ordering = ["-created_at"]


class SignalLog(models.Model):
    """Historical log of signals generated for each user."""
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name="signals")
    symbol = models.CharField(max_length=32, db_index=True)
    interval = models.CharField(max_length=8)
    direction = models.CharField(max_length=10)  # LONG / SHORT / NEUTRAL
    action = models.CharField(max_length=10)     # TRADE / WATCH / WAIT
    entry = models.FloatField()
    stop_loss = models.FloatField()
    take_profit = models.FloatField()
    confidence = models.FloatField()
    risk_reward = models.FloatField()
    regime = models.CharField(max_length=32, blank=True, default="")
    htf_trend = models.CharField(max_length=16, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "signal_log"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.symbol} {self.direction} @ {self.entry} ({self.confidence}%)"
