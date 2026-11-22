from rest_framework import serializers

from .models import Conversation, Message


class AnswerRequestSerializer(serializers.Serializer):
    question = serializers.CharField(max_length=2000)
    use_web = serializers.BooleanField(required=False)
    use_personal = serializers.BooleanField(required=False)


class ChatRequestSerializer(serializers.Serializer):
    message = serializers.CharField(max_length=2000)
    conversation_id = serializers.IntegerField(required=False, allow_null=True)
    use_web = serializers.BooleanField(required=False)
    use_personal = serializers.BooleanField(required=False)


class SummarizeRequestSerializer(serializers.Serializer):
    item_id = serializers.IntegerField(required=False)
    url = serializers.URLField(required=False)
    text = serializers.CharField(required=False, max_length=200000)
    style = serializers.ChoiceField(choices=["concise", "bullets", "detailed"], default="concise")

    def validate(self, attrs):
        if sum(k in attrs for k in ("item_id", "url", "text")) != 1:
            raise serializers.ValidationError("Provide exactly one of item_id, url, or text.")
        return attrs


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ["id", "role", "content", "citations", "created_at"]


class ConversationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Conversation
        fields = ["id", "title", "created_at", "updated_at"]


class ConversationDetailSerializer(ConversationSerializer):
    messages = MessageSerializer(many=True, read_only=True)

    class Meta(ConversationSerializer.Meta):
        fields = ConversationSerializer.Meta.fields + ["messages"]
