from typing import Optional
import logging

from postgrest.exceptions import APIError as PostgrestExceptionAPIError

from dao.dao_base import DAOBase

logger = logging.getLogger(__name__)

class DAOUsers(DAOBase):
    
    def __init__(self):
        super().__init__()
        self._table_name = "users"
        
    def get_users(self, user_id: Optional[str] = None):
        
        try:
            query = self._supabase_client.table(self._table_name)
            query = query.select("*")
            
            if user_id:
                query = query.eq("id", user_id)
            
            query = query.maybe_single()
            result = query.execute()
            if result and result.data:
                return result.data
            
            return None
    
        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - get_users with user_id {user_id}: {e}")
                
        except Exception as e:
            raise Exception(f"error get_users with user_id {user_id}: {e}")

    def update_user_profile(self, user_id: str, data: dict):
        try:
            update_fields = {}
            if "name" in data and data["name"] is not None:
                update_fields["name"] = data["name"]
            if "phone" in data and data["phone"] is not None:
                update_fields["phone"] = data["phone"]
            if "preferred_language" in data and data["preferred_language"] is not None:
                update_fields["preferred_language"] = data["preferred_language"]
            if "avatar_url" in data and data["avatar_url"] is not None:
                update_fields["avatar_url"] = data["avatar_url"]

            if not update_fields:
                return None

            result = (
                self._supabase_client
                .table(self._table_name)
                .update(update_fields)
                .eq("id", user_id)
                .execute()
            )
            return result.data[0] if result and result.data else None

        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - update_user_profile: {e}")
        except Exception as e:
            raise Exception(f"error update_user_profile: {e}")