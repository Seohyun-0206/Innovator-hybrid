from django.contrib import admin

from apps.catalog.models import EvaluationItemResult, EvaluationMethod, LLMModel, RoutingPolicy


@admin.register(LLMModel)
class LLMModelAdmin(admin.ModelAdmin):
    list_display = ("provider", "name", "role", "privacy_level", "is_active")
    list_filter = ("provider", "role", "privacy_level", "is_active")
    search_fields = ("name", "display_name")


@admin.register(RoutingPolicy)
class RoutingPolicyAdmin(admin.ModelAdmin):
    list_display = ("name", "display_name", "is_active")
    search_fields = ("name", "display_name")


@admin.register(EvaluationMethod)
class EvaluationMethodAdmin(admin.ModelAdmin):
    list_display = ("name", "display_name", "method_type", "is_active")
    list_filter = ("method_type", "is_active")
    search_fields = ("name", "display_name")


@admin.register(EvaluationItemResult)
class EvaluationItemResultAdmin(admin.ModelAdmin):
    list_display = ("run", "model", "item_index", "attempt", "predicted_choice", "is_correct", "ok")
    list_filter = ("ok", "is_correct", "strict_ok")
    search_fields = ("question", "raw_output", "error")
