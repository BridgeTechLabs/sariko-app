from postgrest.exceptions import APIError as PostgrestExceptionAPIError

from dao.dao_base import DAOBase


class DAOApiMetrics(DAOBase):
    """history_api_metrics (docs/dev/monitoring Q1): written by services/api_metrics, read by the admin."""

    def __init__(self):
        super().__init__()
        self._table_name = "history_api_metrics"

    def insert_many(self, rows: list) -> None:
        try:
            self._supabase_client.table(self._table_name).insert(rows).execute()
        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - insert api metrics: {e}")

    def delete_before(self, cutoff: str) -> None:
        try:
            self._supabase_client.table(self._table_name).delete().lt("bucket_start", cutoff).execute()
        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - delete api metrics: {e}")
