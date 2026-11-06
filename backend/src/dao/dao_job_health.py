from postgrest.exceptions import APIError as PostgrestExceptionAPIError

from dao.dao_base import DAOBase


class DAOJobHealth(DAOBase):
    """metrics_job_health (docs/dev/20261106-job-health, 20261106-job-control): one row per background job. The backends
    read paused + interval_seconds (set on the admin Monitoring page) and update only the last_* / failures columns."""

    def __init__(self):
        super().__init__()
        self._table_name = "metrics_job_health"

    def read_failures(self, job: str) -> int:
        try:
            result = self._supabase_client.table(self._table_name).select("failures").eq("job", job).maybe_single().execute()
        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - read job health: {e}")
        return result.data["failures"] if result and result.data else 0

    def read_control(self, job: str, default_interval: int) -> dict:
        """{paused, interval_seconds}; a missing row is made with the code's interval (rows come from the migration)."""
        try:
            table = self._supabase_client.table(self._table_name)
            result = table.select("paused, interval_seconds").eq("job", job).maybe_single().execute()
            if result and result.data:
                return result.data
            table.upsert({"job": job, "interval_seconds": default_interval}, on_conflict="job", ignore_duplicates=True).execute()
            return {"paused": False, "interval_seconds": default_interval}
        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - read job control: {e}")

    def update(self, job: str, values: dict) -> None:
        try:
            self._supabase_client.table(self._table_name).update(values).eq("job", job).execute()
        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - write job health: {e}")
