from rest_framework import serializers
from .models import StringRecord

class StringRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = StringRecord
        fields = "__all__"
