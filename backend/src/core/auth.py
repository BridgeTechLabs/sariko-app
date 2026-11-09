import logging
import os
import jwt

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from clients.supabase import get_supabase_client

oauth2_scheme = HTTPBearer()
SUPABASE_JWKS_URL = os.getenv("SUPABASE_JWKS_URL", None)
SUPABASE_JWT_ALGORITHM = os.getenv("SUPABASE_JWT_ALGORITHM", "ES256")  # Supabase defaults to HS256

logger = logging.getLogger(__name__) 

if SUPABASE_JWKS_URL is None:
    logger.exception('Not found SUPABASE_JWKS_URL')
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED
    )
    
jwks_client = jwt.PyJWKClient(SUPABASE_JWKS_URL)

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(oauth2_scheme)):

    try:
        token = credentials.credentials
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(token, signing_key.key, algorithms=[SUPABASE_JWT_ALGORITHM], audience="authenticated")
        user_id = payload.get('sub')
        user_metadata = payload.get('user_metadata', {})
        return {"id": user_id, **user_metadata}
    
    except Exception as e:
        logger.exception(f"{repr(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED
        )