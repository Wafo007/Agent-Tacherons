"""Endpoints d'authentification : inscription, connexion."""

from fastapi import APIRouter, HTTPException, status

from src.application.use_cases.auth.login_user import LoginUserUseCase
from src.application.use_cases.auth.refresh_token import RefreshTokenUseCase
from src.application.use_cases.auth.register_user import RegisterUserDTO, RegisterUserUseCase
from src.core.dependencies import UserRepo
from src.core.exceptions import EmailAlreadyExistsError, UnauthorizedError
from src.presentation.schemas.auth_schema import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequest, user_repository: UserRepo) -> UserResponse:
    use_case = RegisterUserUseCase(user_repository)
    try:
        user = await use_case.execute(
            RegisterUserDTO(
                email=request.email,
                full_name=request.full_name,
                plain_password=request.password,
                timezone=request.timezone,
            )
        )
    except EmailAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return UserResponse(
        id=user.id, email=user.email, full_name=user.full_name, timezone=user.timezone, is_active=user.is_active
    )


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, user_repository: UserRepo) -> TokenResponse:
    use_case = LoginUserUseCase(user_repository)
    try:
        result = await use_case.execute(request.email, request.password)
    except UnauthorizedError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    return TokenResponse(access_token=result.access_token, refresh_token=result.refresh_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(request: RefreshRequest, user_repository: UserRepo) -> TokenResponse:
    """Échange un refresh token valide contre une nouvelle paire access/refresh.

    Retourne 401 (jamais 403) si le refresh token est invalide, expiré, ou si
    l'utilisateur associé n'existe plus / a été désactivé : dans tous ces cas
    le frontend doit déconnecter proprement l'utilisateur plutôt que réessayer.
    """
    use_case = RefreshTokenUseCase(user_repository)
    try:
        result = await use_case.execute(request.refresh_token)
    except UnauthorizedError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    return TokenResponse(access_token=result.access_token, refresh_token=result.refresh_token)
