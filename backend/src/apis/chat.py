import logging

from fastapi import APIRouter, HTTPException, Depends, status, Query

from core.auth import verify_token
from dao.dao_chat_conversations import DAOChatConversations
from dao.dao_chat_messages import DAOChatMessages
from dao.dao_seller_profiles import DAOSellerProfiles
from schemas import Schema

router = APIRouter(prefix="/chat")
logger = logging.getLogger(__name__)


def _resolve_side(conversation: dict, user: dict) -> str:
    """Return 'buyer' or 'seller' for the caller, or 403 if not a participant.
    Backend uses the service_role key (bypasses RLS), so participation is
    enforced here."""
    if conversation["buyer_id"] == user["id"]:
        return "buyer"
    profile = DAOSellerProfiles().read_seller_profile_by_user_id(user["id"])
    if profile and profile["id"] == conversation["seller_id"]:
        return "seller"
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


@router.post("/conversations")
def create_conversation(request: Schema.RequestCreateConversation, user=Depends(verify_token)):
    """Buyer opens (or re-opens) a chat with a seller. Idempotent per (buyer, seller)."""
    dao_sellers = DAOSellerProfiles()
    seller = dao_sellers.read_seller_by_slug_name(request.seller_slug)
    if not seller:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Seller not found")

    owner = dao_sellers.read_seller_user_id_by_seller_id(seller["id"])
    if owner and owner["user_id"] == user["id"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot start a conversation with your own store")

    dao_conv = DAOChatConversations()
    conversation = dao_conv.get_or_create(buyer_id=user["id"], seller_id=seller["id"])
    if not conversation:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create conversation")

    return {"success": True, "conversation": conversation}


@router.get("/conversations")
def list_conversations(as_seller: bool = Query(False), user=Depends(verify_token)):
    """List the caller's conversations (buyer view by default, seller view when as_seller)."""
    dao_conv = DAOChatConversations()

    if as_seller:
        profile = DAOSellerProfiles().read_seller_profile_by_user_id(user["id"])
        if not profile:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a seller")
        conversations = dao_conv.list_for_seller(profile["id"])
        # defensive: never surface a self-conversation (buyer == this seller's owner)
        conversations = [c for c in conversations if c.get("buyer_id") != user["id"]]
    else:
        conversations = dao_conv.list_for_buyer(user["id"])

    conversation_ids = [c["id"] for c in conversations]
    unread_map = {}
    if conversation_ids:
        rows = DAOChatMessages().read_unread_rows(conversation_ids, reader_id=user["id"])
        for row in rows:
            cid = row["conversation_id"]
            unread_map[cid] = unread_map.get(cid, 0) + 1

    pin_col = "seller_pinned_at" if as_seller else "buyer_pinned_at"
    for c in conversations:
        c["unread_count"] = unread_map.get(c["id"], 0)
        c["pinned"] = bool(c.get(pin_col))

    return {"success": True, "conversations": conversations}


@router.patch("/conversations/{conversation_id}/read")
def mark_conversation_read(conversation_id: str, user=Depends(verify_token)):
    """Mark incoming messages as read. Caller must be a participant (enforced here,
    since the backend uses the service_role key which bypasses RLS)."""
    dao_conv = DAOChatConversations()
    conversation = dao_conv.read_by_id(conversation_id)
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    _resolve_side(conversation, user)  # 403 if not a participant

    DAOChatMessages().mark_read(conversation_id=conversation_id, reader_id=user["id"])
    return {"success": True}


@router.patch("/conversations/{conversation_id}/pin")
def set_conversation_pinned(conversation_id: str, request: Schema.RequestSetPinned, user=Depends(verify_token)):
    """Pin/unpin a conversation to the top of the caller's own inbox."""
    dao_conv = DAOChatConversations()
    conversation = dao_conv.read_by_id(conversation_id)
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    side = _resolve_side(conversation, user)
    dao_conv.set_pinned(conversation_id, side, request.pinned)
    return {"success": True, "pinned": request.pinned}


@router.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id: str, user=Depends(verify_token)):
    """Soft-delete a conversation from the caller's own inbox. A later message
    resurfaces it (bump trigger clears the flag)."""
    dao_conv = DAOChatConversations()
    conversation = dao_conv.read_by_id(conversation_id)
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    side = _resolve_side(conversation, user)
    dao_conv.soft_delete(conversation_id, side)
    return {"success": True}
