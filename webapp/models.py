
from django.db import models


class ComparisonRun(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)

    baseline_trace_count = models.PositiveIntegerField()
    degraded_trace_count = models.PositiveIntegerField()
    matched_operation_count = models.PositiveIntegerField()
    regression_count = models.PositiveIntegerField()

    baseline_dataset = models.JSONField()
    degraded_dataset = models.JSONField()
    results = models.JSONField()

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return (
            f"Comparison {self.pk}: "
            f"{self.baseline_trace_count} baseline traces, "
            f"{self.degraded_trace_count} degraded traces"
        )
