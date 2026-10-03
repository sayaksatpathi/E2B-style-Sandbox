from fastapi import APIRouter, HTTPException
from api.schemas import TokenRequest, TokenResponse
from api.auth import create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES

router = APIRouter()


@router.post("/token", response_model=TokenResponse)
async def issue_token(body: TokenRequest):
    """
    Issue a JWT for the given user_id.
    In production this endpoint would validate against a user store.
    Here it's a simple dev endpoint — protect or remove before deploying publicly.
    """
    token = create_access_token(body.user_id)
    return TokenResponse(
        access_token=token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
