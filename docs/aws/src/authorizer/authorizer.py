"""Lambda authorizer — επαληθεύει JWT από τον third-party OIDC provider.

Το REST API δεν έχει native JWT authorizer όπως το HTTP API· η επαλήθευση
γίνεται εδώ, σε κώδικα. Το αντίτιμο είναι ένα επιπλέον invocation ανά
αίτημα — γι' αυτό το αποτέλεσμα γίνεται cache από το API Gateway
(ReauthorizeEvery στο template).

Επαληθεύονται: υπογραφή (RS256 μέσω JWKS), iss, aud, exp.
"""

import json
import os
import urllib.request

import jwt
from jwt import PyJWKClient

ISSUER = os.environ["OIDC_ISSUER"].rstrip("/")
AUDIENCE = os.environ["OIDC_AUDIENCE"]

# Ένα container εξυπηρετεί πολλά αιτήματα: το JWKS κατεβαίνει μία φορά.
_jwk_client = None


def _get_jwk_client() -> PyJWKClient:
    global _jwk_client
    if _jwk_client is None:
        discovery = f"{ISSUER}/.well-known/openid-configuration"
        with urllib.request.urlopen(discovery, timeout=5) as response:
            jwks_uri = json.load(response)["jwks_uri"]
        _jwk_client = PyJWKClient(jwks_uri)
    return _jwk_client


def _bearer(event: dict) -> str:
    """Το API Gateway δεν κανονικοποιεί το casing των headers."""
    headers = event.get("headers") or {}
    raw = next(
        (v for k, v in headers.items() if k.lower() == "authorization"), ""
    )
    scheme, _, token = raw.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise ValueError("λείπει το Authorization: Bearer <token>")
    return token


def _policy(principal: str, effect: str, resource: str, claims: dict) -> dict:
    return {
        "principalId": principal,
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [{
                "Action": "execute-api:Invoke",
                "Effect": effect,
                "Resource": resource,
            }],
        },
        # Φτάνει στη Lambda ως requestContext.authorizer — έτσι ξέρει ποιος
        # έστειλε το alert χωρίς να ξαναδιαβάσει το token.
        "context": {
            "sub": str(claims.get("sub", "")),
            "email": str(claims.get("email", "")),
        },
    }


def _stage_arn(method_arn: str) -> str:
    """arn:...:api-id/stage/GET/alerts -> arn:...:api-id/stage/*

    Το policy πρέπει να καλύπτει όλο το stage: το API Gateway κάνει cache
    την απάντηση ανά token, και ένα policy δεμένο σε ένα μόνο method θα
    απέρριπτε το επόμενο αίτημα σε άλλο path.
    """
    head, _, tail = method_arn.partition("/")
    stage = tail.split("/")[0] if tail else "*"
    return f"{head}/{stage}/*"


def handler(event, context):
    resource = _stage_arn(event.get("methodArn", ""))

    try:
        token = _bearer(event)
        signing_key = _get_jwk_client().get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=AUDIENCE,
            issuer=ISSUER,
        )
    except Exception as exc:                       # noqa: BLE001
        # Το string 'Unauthorized' είναι συμβόλαιο με το API Gateway: μόνο
        # αυτό γυρίζει 401. Οτιδήποτε άλλο γίνεται 500.
        print(f"απορρίφθηκε: {type(exc).__name__}: {exc}")
        raise Exception("Unauthorized")            # noqa: TRY002

    return _policy(claims.get("sub", "unknown"), "Allow", resource, claims)
