"""SQLite table models and CRUD helpers."""

from telesoft.db.models.channel import (
    ChannelRow,
    create_channel,
    delete_channel,
    get_channel,
    get_channel_by_telegram_id,
    list_channels,
    update_channel,
)
from telesoft.db.models.job import (
    JobRow,
    create_job,
    delete_job,
    get_job,
    list_jobs,
    update_job_status,
)
from telesoft.db.models.log import (
    LogRow,
    create_log,
    delete_logs,
    list_logs,
)
from telesoft.db.models.pattern import (
    PatternRow,
    create_pattern,
    delete_pattern,
    get_pattern,
    list_patterns,
)

__all__ = [
    "ChannelRow",
    "JobRow",
    "LogRow",
    "PatternRow",
    "create_channel",
    "create_job",
    "create_log",
    "create_pattern",
    "delete_channel",
    "delete_job",
    "delete_logs",
    "delete_pattern",
    "get_channel",
    "get_channel_by_telegram_id",
    "get_job",
    "get_pattern",
    "list_channels",
    "list_jobs",
    "list_logs",
    "list_patterns",
    "update_channel",
    "update_job_status",
]
