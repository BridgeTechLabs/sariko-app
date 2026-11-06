from postgrest.exceptions import APIError as PostgrestExceptionAPIError

from dao.dao_base import DAOBase


class DAOJobHealth(DAOBase):
    """metrics_job_health (docs/dev/20261106-job-health): one row per background job, written by services/job_health,
    read by the admin Monitoring page."""

    def __init__(self):
        super().__init__()
        self._table_name = "metrics_job_health"

    def read_failures(self, job: str) -> int:
        try:
            result = self._supabase_client.table(self._table_name).select("failures").eq("job", job).maybe_single().execute()
        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - read job health: {e}")
        return result.data["failures"] if result and result.data else 0

    def upsert(self, row: dict) -> None:
        try:
            self._supabase_client.table(self._table_name).upsert(row, on_conflict="job").execute()
        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - write job health: {e}")
