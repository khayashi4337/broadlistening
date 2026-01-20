#!/usr/bin/env python3
"""
認証モジュール - LDAP/OIDC対応

複数の認証方式をサポート:
- APIキー認証（シンプル）
- LDAP認証（企業向け）
- OIDC認証（SSO対応）

環境変数:
    AUTH_METHOD: 認証方式 (apikey, ldap, oidc)

    # APIキー認証
    BROADLISTENING_API_KEY: APIキー

    # LDAP認証
    LDAP_SERVER: LDAPサーバーURL (例: ldap://ldap.example.com)
    LDAP_BASE_DN: ベースDN (例: dc=example,dc=com)
    LDAP_USER_DN_TEMPLATE: ユーザーDNテンプレート (例: uid={username},ou=users)
    LDAP_BIND_DN: バインドDN（検索用）
    LDAP_BIND_PASSWORD: バインドパスワード

    # OIDC認証
    OIDC_ISSUER: OIDCプロバイダーURL
    OIDC_CLIENT_ID: クライアントID
    OIDC_CLIENT_SECRET: クライアントシークレット
    OIDC_REDIRECT_URI: コールバックURL
"""

import os
import logging
import hashlib
import hmac
import time
from functools import wraps
from typing import Optional, List, Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# ===== 設定 =====

AUTH_METHOD = os.getenv("AUTH_METHOD", "apikey").lower()

# APIキー設定
API_KEY = os.getenv("BROADLISTENING_API_KEY", "")

# LDAP設定
LDAP_CONFIG = {
    "server": os.getenv("LDAP_SERVER", ""),
    "base_dn": os.getenv("LDAP_BASE_DN", ""),
    "user_dn_template": os.getenv("LDAP_USER_DN_TEMPLATE", "uid={username},ou=users"),
    "bind_dn": os.getenv("LDAP_BIND_DN", ""),
    "bind_password": os.getenv("LDAP_BIND_PASSWORD", ""),
}

# OIDC設定
OIDC_CONFIG = {
    "issuer": os.getenv("OIDC_ISSUER", ""),
    "client_id": os.getenv("OIDC_CLIENT_ID", ""),
    "client_secret": os.getenv("OIDC_CLIENT_SECRET", ""),
    "redirect_uri": os.getenv("OIDC_REDIRECT_URI", ""),
}


@dataclass
class AuthResult:
    """認証結果"""
    success: bool
    user_id: Optional[str] = None
    username: Optional[str] = None
    email: Optional[str] = None
    roles: Optional[list] = None
    error: Optional[str] = None


# ===== APIキー認証 =====

def verify_api_key(provided_key: str) -> AuthResult:
    """APIキーを検証"""
    if not API_KEY:
        # APIキーが設定されていない場合は認証不要
        return AuthResult(success=True, user_id="anonymous")

    if not provided_key:
        return AuthResult(success=False, error="API key required")

    # タイミング攻撃対策のため、hmac.compare_digestを使用
    if hmac.compare_digest(provided_key, API_KEY):
        return AuthResult(success=True, user_id="api_user")

    return AuthResult(success=False, error="Invalid API key")


# ===== LDAP認証 =====

def verify_ldap(username: str, password: str) -> AuthResult:
    """LDAP認証"""
    if not LDAP_CONFIG["server"]:
        return AuthResult(success=False, error="LDAP not configured")

    try:
        # ldap3ライブラリを遅延インポート（オプション依存）
        from ldap3 import Server, Connection, ALL, SUBTREE
        from ldap3.core.exceptions import LDAPException
    except ImportError:
        logger.error("ldap3 library not installed. Run: pip install ldap3")
        return AuthResult(success=False, error="LDAP library not available")

    try:
        server = Server(LDAP_CONFIG["server"], get_info=ALL)

        # ユーザーDNを構築
        user_dn = LDAP_CONFIG["user_dn_template"].format(username=username)
        if LDAP_CONFIG["base_dn"]:
            user_dn = f"{user_dn},{LDAP_CONFIG['base_dn']}"

        # バインド試行
        conn = Connection(server, user=user_dn, password=password)

        if not conn.bind():
            logger.warning(f"LDAP bind failed for user: {username}")
            return AuthResult(success=False, error="Invalid credentials")

        # ユーザー情報を取得
        search_filter = f"(uid={username})"
        conn.search(
            LDAP_CONFIG["base_dn"],
            search_filter,
            search_scope=SUBTREE,
            attributes=["uid", "mail", "cn", "memberOf"]
        )

        user_info = {}
        if conn.entries:
            entry = conn.entries[0]
            user_info = {
                "uid": str(entry.uid) if hasattr(entry, "uid") else username,
                "email": str(entry.mail) if hasattr(entry, "mail") else None,
                "name": str(entry.cn) if hasattr(entry, "cn") else None,
                "groups": list(entry.memberOf) if hasattr(entry, "memberOf") else [],
            }

        conn.unbind()

        return AuthResult(
            success=True,
            user_id=user_info.get("uid", username),
            username=username,
            email=user_info.get("email"),
            roles=user_info.get("groups", [])
        )

    except LDAPException as e:
        logger.error(f"LDAP error: {e}")
        return AuthResult(success=False, error="LDAP error")
    except Exception as e:
        logger.error(f"Unexpected LDAP error: {e}")
        return AuthResult(success=False, error="Authentication error")


# ===== OIDC認証 =====

def get_oidc_authorization_url(state: str) -> Optional[str]:  # noqa: ARG001
    """OIDC認可URLを生成"""
    if not OIDC_CONFIG["issuer"]:
        return None

    params = {
        "client_id": OIDC_CONFIG["client_id"],
        "redirect_uri": OIDC_CONFIG["redirect_uri"],
        "response_type": "code",
        "scope": "openid profile email",
        "state": state,
    }

    # URLを構築
    from urllib.parse import urlencode
    auth_endpoint = f"{OIDC_CONFIG['issuer']}/authorize"
    return f"{auth_endpoint}?{urlencode(params)}"


def verify_oidc_callback(code: str, state: str) -> AuthResult:
    """OIDCコールバックを検証"""
    if not OIDC_CONFIG["issuer"]:
        return AuthResult(success=False, error="OIDC not configured")

    try:
        import requests
    except ImportError:
        logger.error("requests library not installed")
        return AuthResult(success=False, error="HTTP library not available")

    try:
        # トークンエンドポイントにリクエスト
        token_endpoint = f"{OIDC_CONFIG['issuer']}/token"
        token_response = requests.post(
            token_endpoint,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": OIDC_CONFIG["redirect_uri"],
                "client_id": OIDC_CONFIG["client_id"],
                "client_secret": OIDC_CONFIG["client_secret"],
            },
            timeout=10
        )

        if token_response.status_code != 200:
            logger.error(f"Token exchange failed: {token_response.status_code}")
            return AuthResult(success=False, error="Token exchange failed")

        tokens = token_response.json()
        access_token = tokens.get("access_token")

        if not access_token:
            return AuthResult(success=False, error="No access token received")

        # ユーザー情報を取得
        userinfo_endpoint = f"{OIDC_CONFIG['issuer']}/userinfo"
        userinfo_response = requests.get(
            userinfo_endpoint,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10
        )

        if userinfo_response.status_code != 200:
            logger.error(f"Userinfo request failed: {userinfo_response.status_code}")
            return AuthResult(success=False, error="Failed to get user info")

        userinfo = userinfo_response.json()

        return AuthResult(
            success=True,
            user_id=userinfo.get("sub"),
            username=userinfo.get("preferred_username"),
            email=userinfo.get("email"),
            roles=userinfo.get("groups", [])
        )

    except requests.RequestException as e:
        logger.error(f"OIDC request error: {e}")
        return AuthResult(success=False, error="OIDC request failed")
    except Exception as e:
        logger.error(f"Unexpected OIDC error: {e}")
        return AuthResult(success=False, error="Authentication error")


# ===== JWT トークン生成・検証 =====

JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-production")
JWT_EXPIRY = int(os.getenv("JWT_EXPIRY", "3600"))  # 1時間


def generate_token(user_id: str, username: str, roles: Optional[List[str]] = None) -> str:
    """シンプルなJWTトークンを生成（外部ライブラリ不要）"""
    import base64
    import json

    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": user_id,
        "username": username,
        "roles": roles or [],
        "iat": int(time.time()),
        "exp": int(time.time()) + JWT_EXPIRY,
    }

    # Base64エンコード
    def b64encode(data: dict) -> str:
        return base64.urlsafe_b64encode(
            json.dumps(data).encode()
        ).rstrip(b"=").decode()

    header_b64 = b64encode(header)
    payload_b64 = b64encode(payload)

    # 署名
    message = f"{header_b64}.{payload_b64}"
    signature = hmac.new(
        JWT_SECRET.encode(),
        message.encode(),
        hashlib.sha256
    ).digest()
    signature_b64 = base64.urlsafe_b64encode(signature).rstrip(b"=").decode()

    return f"{header_b64}.{payload_b64}.{signature_b64}"


def verify_token(token: str) -> AuthResult:
    """JWTトークンを検証"""
    import base64
    import json

    try:
        parts = token.split(".")
        if len(parts) != 3:
            return AuthResult(success=False, error="Invalid token format")

        header_b64, payload_b64, signature_b64 = parts

        # 署名検証
        message = f"{header_b64}.{payload_b64}"
        expected_signature = hmac.new(
            JWT_SECRET.encode(),
            message.encode(),
            hashlib.sha256
        ).digest()
        expected_b64 = base64.urlsafe_b64encode(expected_signature).rstrip(b"=").decode()

        if not hmac.compare_digest(signature_b64, expected_b64):
            return AuthResult(success=False, error="Invalid signature")

        # ペイロードをデコード
        # パディングを追加
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += "=" * padding

        payload = json.loads(base64.urlsafe_b64decode(payload_b64))

        # 有効期限チェック
        if payload.get("exp", 0) < time.time():
            return AuthResult(success=False, error="Token expired")

        return AuthResult(
            success=True,
            user_id=payload.get("sub"),
            username=payload.get("username"),
            roles=payload.get("roles", [])
        )

    except Exception as e:
        logger.error(f"Token verification error: {e}")
        return AuthResult(success=False, error="Invalid token")


# ===== 統合認証関数 =====

def authenticate(request) -> AuthResult:
    """リクエストを認証（設定された方式を使用）"""

    # Bearer トークンをチェック
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]

        # JWTトークンかAPIキーかを判定
        if "." in token:
            return verify_token(token)
        else:
            return verify_api_key(token)

    # APIキーパラメータをチェック
    api_key = request.args.get("api_key", "")
    if api_key:
        return verify_api_key(api_key)

    # Basic認証をチェック（LDAP用）
    if AUTH_METHOD == "ldap" and auth_header.startswith("Basic "):
        import base64
        try:
            credentials = base64.b64decode(auth_header[6:]).decode()
            username, password = credentials.split(":", 1)
            return verify_ldap(username, password)
        except Exception:
            return AuthResult(success=False, error="Invalid Basic auth")

    # 認証情報なし
    if not API_KEY and AUTH_METHOD == "apikey":
        # APIキーが設定されていない場合は認証不要
        return AuthResult(success=True, user_id="anonymous")

    return AuthResult(success=False, error="Authentication required")


def require_auth(f: Callable) -> Callable:
    """認証必須デコレータ"""
    @wraps(f)
    def decorated(*args, **kwargs):
        from flask import request, jsonify, g

        result = authenticate(request)

        if not result.success:
            return jsonify({
                "error": "Unauthorized",
                "message": result.error
            }), 401

        # 認証情報をリクエストコンテキストに保存
        g.user_id = result.user_id
        g.username = result.username
        g.roles = result.roles or []

        return f(*args, **kwargs)
    return decorated


def require_role(role: str) -> Callable:
    """特定ロール必須デコレータ"""
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated(*args, **kwargs):
            from flask import request, jsonify, g

            result = authenticate(request)

            if not result.success:
                return jsonify({
                    "error": "Unauthorized",
                    "message": result.error
                }), 401

            if role not in (result.roles or []):
                return jsonify({
                    "error": "Forbidden",
                    "message": f"Role '{role}' required"
                }), 403

            g.user_id = result.user_id
            g.username = result.username
            g.roles = result.roles or []

            return f(*args, **kwargs)
        return decorated
    return decorator
