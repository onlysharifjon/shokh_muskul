from django.db import models

class User(models.Model):
    telegram_id = models.BigIntegerField(unique=True)
    username = models.CharField(max_length=150, blank=True, null=True)
    first_name = models.CharField(max_length=150, blank=True, null=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.username or str(self.telegram_id)


class CalorieRecord(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='records')
    height = models.FloatField()
    weight = models.FloatField()
    age = models.IntegerField()
    gender = models.CharField(max_length=10)
    activity = models.FloatField()
    goal = models.CharField(max_length=32)
    tdee = models.FloatField()
    protein = models.FloatField()
    fat = models.FloatField()
    carb = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} - {self.goal} ({round(self.tdee)} kcal)"
