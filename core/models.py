from django.db import models

# Create your models here.
class StringRecord(models.Model):
    value = models.TextField(unique=True)
    sha256_hash = models.CharField(max_length=64, unique=True)
    properties = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.value