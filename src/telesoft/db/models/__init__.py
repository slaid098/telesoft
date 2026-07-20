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

__all__ = [
    "ChannelRow",
    "JobRow",
    "LogRow",
    "create_channel",
    "create_job",
    "create_log",
    "delete_channel",
    "delete_job",
    "delete_logs",
    "get_channel",
    "get_channel_by_telegram_id",
    "get_job",
    "list_channels",
    "list_jobs",
    "list_logs",
    "update_channel",
    "update_job_status",
]
