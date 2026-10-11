from typing import Optional
import logging

from postgrest.exceptions import APIError as PostgrestExceptionAPIError

from core.store_hours import is_open_now, with_open_now
from dao.dao_base import DAOBase

logger = logging.getLogger(__name__)

class DAOSellerProfiles(DAOBase):
    
    def __init__(self):
        super().__init__()
        self._table_name = "seller_profiles"
        
    
    def read_founding_sellers(self):
        try:
            query = self._supabase_client.table(self._table_name)
            query = query.select("id, user_id, store_name, slug, avatar_url, status, is_open, opening_time, closing_time")
            query = query.eq("is_listed", True)
            query = query.order("status").order("display_order").order("created_at")

            result = query.execute()
            
            if result and result.data:
                sellers = [with_open_now(s) for s in result.data]
                # active before coming_soon, then open-now before closed; stable, so display_order holds within each block
                return sorted(sellers, key=lambda s: (s["status"] != "active", not s["is_open"]))
                
            return None
            
        # except PostgrestExceptionAPIError as e:
        #     raise Exception(f"Supabase error - read_seller_id_by_slug_name with slug {slug}: {e}")
                
        except Exception as e:
            raise Exception(f"error read_founding_sellers: {e}")
        
    
    def read_seller_by_slug_name(self, slug: str):
        try:
            query = self._supabase_client.table(self._table_name)
            query = query.select("id, store_name, slug, address, avatar_url, status, is_verified, phone, lat, lon, tier, description, is_open, opening_time, closing_time, rating_avg, rating_count").eq("slug", slug)
            
            query = query.maybe_single()
            result = query.execute()
            
            if result and result.data:
                return with_open_now(result.data)
                
            return None
            
        # except PostgrestExceptionAPIError as e:
        #     raise Exception(f"Supabase error - read_seller_id_by_slug_name with slug {slug}: {e}")
                
        except Exception as e:
            raise Exception(f"error read_seller_id_by_slug_name with slug {slug}: {e}")
            
        
    def read_seller_profile_by_user_id(self, user_id: str):
        try:
            result = (
                self._supabase_client
                .table(self._table_name)
                .select("id, store_name, slug, avatar_url, address, phone, lat, lon, rating_avg, rating_count, is_open, opening_time, closing_time")
                .eq("user_id", user_id)
                .maybe_single()
                .execute()
            )
            return result.data if result and result.data else None

        except Exception as e:
            raise Exception(f"error read_seller_profile_by_user_id: {e}")
    
    def read_seller_coords_by_id(self, seller_id: str):
        try:
            result = (
                self._supabase_client
                .table(self._table_name)
                .select("id, store_name, address, lat, lon")
                .eq("id", seller_id)
                .maybe_single()
                .execute()
            )
            return result.data if result and result.data else None

        except Exception as e:
            raise Exception(f"error read_seller_coords_by_id: {e}")

    def read_store_slug_name_by_seller_id(self, seller_id):
        
        try:
            query = self._supabase_client.table(self._table_name)
            query = query.select("slug").eq("id", seller_id)
            
            query = query.maybe_single()
            result = query.execute()
            if result and result.data:
                return result.data
                
            return None
        
        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - read_store_slug_name_by_seller_id with seller_id {seller_id}: {e}")
                
        except Exception as e:
            raise Exception(f"error read_store_slug_name_by_seller_id with seller_id {seller_id}: {e}")
        
        
    def read_seller_user_id_by_seller_id(self, seller_id):

        try:
            query = self._supabase_client.table(self._table_name)
            query = query.select("user_id").eq("id", seller_id)

            query = query.maybe_single()
            result = query.execute()
            if result and result.data:
                return result.data

            return None

        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - read_seller_user_id_by_seller_id with seller_id {seller_id}: {e}")

        except Exception as e:
            raise Exception(f"error read_seller_user_id_by_seller_id with seller_id {seller_id}: {e}")

    def update_seller_profile_info(self, user_id: str, data: dict):
        try:
            allowed = {"phone", "address", "lat", "lon", "store_name", "is_open", "opening_time", "closing_time"}
            update_fields = {k: v for k, v in data.items() if k in allowed}
            if not update_fields:
                return None
            result = (
                self._supabase_client
                .table(self._table_name)
                .update(update_fields)
                .eq("user_id", user_id)
                .execute()
            )
            return result.data[0] if result and result.data else None
        except Exception as e:
            raise Exception(f"error update_seller_profile_info: {e}")

    def update_avatar_url(self, user_id: str, avatar_url: str):
        try:
            result = (
                self._supabase_client
                .table(self._table_name)
                .update({"avatar_url": avatar_url})
                .eq("user_id", user_id)
                .execute()
            )
            return result.data[0] if result and result.data else None
        except Exception as e:
            raise Exception(f"error update_avatar_url: {e}")

    def read_seller_order_info(self, seller_id: str):
        """Fetch user_id + effective commission rate in one query for order creation."""
        try:
            result = (
                self._supabase_client
                .table(self._table_name)
                .select("user_id, is_open, opening_time, closing_time, commission_rate_override, admin_tier_config(commission_rate)")
                .eq("id", seller_id)
                .maybe_single()
                .execute()
            )
            if not result or not result.data:
                return None
            row = result.data
            tier_rate = row["admin_tier_config"]["commission_rate"]
            effective_rate = row["commission_rate_override"] if row["commission_rate_override"] is not None else tier_rate
            return {
                "user_id": row["user_id"],
                "is_open": is_open_now(row["is_open"], row["opening_time"], row["closing_time"]),
                "commission_rate": float(effective_rate),
            }
        except PostgrestExceptionAPIError as e:
            raise Exception(f"Supabase error - read_seller_order_info: {e}")
        except Exception as e:
            raise Exception(f"error read_seller_order_info: {e}")
            
        