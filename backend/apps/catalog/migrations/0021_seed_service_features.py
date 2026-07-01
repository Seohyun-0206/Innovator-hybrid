from django.db import migrations


SERVICE_FEATURES = [
    {
        "name": "General FAQ",
        "description": "Simple factual questions and FAQ responses requiring fast turnaround",
        "required_tier": "lightweight",
        "routing_path": "lightweight",
        "condition_key": "general",
        "main_metrics": ["Accuracy", "Latency"],
        "sort_order": 10,
    },
    {
        "name": "Business QA",
        "description": "General business queries and workplace Q&A requiring balanced performance",
        "required_tier": "standard",
        "routing_path": "standard",
        "condition_key": "general",
        "main_metrics": ["Accuracy", "Latency", "Human Review"],
        "sort_order": 20,
    },
    {
        "name": "Policy / Regulation QA",
        "description": "Compliance and regulation questions requiring high accuracy and source alignment",
        "required_tier": "advanced",
        "routing_path": "advanced",
        "condition_key": "reasoning",
        "main_metrics": ["Accuracy", "Source Alignment"],
        "sort_order": 30,
    },
    {
        "name": "SQL / JSON Generation",
        "description": "Structured output generation requiring format compliance validation",
        "required_tier": "structured",
        "routing_path": "structured",
        "condition_key": "structured_output",
        "main_metrics": ["Format Success Rate"],
        "sort_order": 40,
    },
    {
        "name": "RAG Document QA",
        "description": "Retrieval-augmented generation over large documents requiring long context handling",
        "required_tier": "long_context",
        "routing_path": "long_context",
        "condition_key": "long_context",
        "main_metrics": ["Retrieval Relevance", "Source Alignment"],
        "sort_order": 50,
    },
    {
        "name": "Meeting Analysis",
        "description": "Meeting transcript summarization and information extraction from long documents",
        "required_tier": "long_context",
        "routing_path": "long_context",
        "condition_key": "long_context",
        "main_metrics": ["Information Extraction Accuracy"],
        "sort_order": 60,
    },
    {
        "name": "Revalidation Request",
        "description": "Re-checking and validating prior responses requiring advanced reasoning",
        "required_tier": "advanced",
        "routing_path": "escalation",
        "condition_key": "reasoning",
        "main_metrics": ["Response Reliability", "Error Correction Rate"],
        "sort_order": 70,
    },
]


def seed_service_features(apps, schema_editor):
    ServiceFeature = apps.get_model("catalog", "ServiceFeature")
    for feature in SERVICE_FEATURES:
        ServiceFeature.objects.update_or_create(
            name=feature["name"],
            defaults=feature,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0020_servicefeature_policydraft"),
    ]

    operations = [
        migrations.RunPython(seed_service_features, migrations.RunPython.noop),
    ]
