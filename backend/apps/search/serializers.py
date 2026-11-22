from rest_framework import serializers

from .models import SearchQuery


class WebSearchRequestSerializer(serializers.Serializer):
    query = serializers.CharField(max_length=500)
    limit = serializers.IntegerField(min_value=1, max_value=20, default=10)
    time_range = serializers.ChoiceField(choices=["day", "week", "month", "year"], required=False)
    category = serializers.ChoiceField(
        choices=["all", "images", "news", "videos", "maps", "shopping"],
        default="all",
        required=False,
    )


class PersonalSearchRequestSerializer(serializers.Serializer):
    query = serializers.CharField(max_length=500)
    limit = serializers.IntegerField(min_value=1, max_value=50, default=10)
    kind = serializers.ChoiceField(choices=["note", "bookmark", "document"], required=False)
    collection = serializers.IntegerField(required=False)
    tag = serializers.CharField(max_length=50, required=False)
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)


class SearchQuerySerializer(serializers.ModelSerializer):
    class Meta:
        model = SearchQuery
        fields = ["id", "mode", "query", "filters", "result_count", "created_at"]
