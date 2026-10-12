import base64
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import requests

BASE_URL = "https://api.improvmx.com/v3"

class ImprovMxError(RuntimeError):
    def __init__(self, status: int, payload: Any):
        self.status = status
        self.payload = payload
        super().__init__(f"HTTP {status}: {payload}")

def _basic_auth_header(token: str) -> str:
    raw = f"api:{token}".encode("utf-8")
    b64 = base64.b64encode(raw).decode("ascii")
    return f"Basic {b64}"

@dataclass
class Domain:
    domain: str
    active: bool
    display: str
    added: Optional[int] = None
    notification_email: Optional[str] = None
    whitelabel: Optional[str] = None

@dataclass
class Alias:
    id: int
    alias: str
    forward: str
    created: Optional[int] = None

class ImprovMxClient:
    def __init__(self, token: str, timeout: float = 20.0):
        self.token = token.strip()
        self.timeout = timeout

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": _basic_auth_header(self.token),
            "Accept": "application/json"
        }

    def _request(self, method: str, path: str, params: Optional[Dict[str, Any]] = None, json_body: Optional[Dict[str, Any]] = None) -> Any:
        url = BASE_URL + path
        headers = self._headers()
        if json_body is not None:
            headers["Content-Type"] = "application/json"
        r = requests.request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            json=json_body,
            timeout=self.timeout
        )
        try:
            payload = r.json()
        except Exception:
            payload = {"success": False, "raw": r.text}
        if r.status_code >= 400 or (isinstance(payload, dict) and payload.get("success") is False and r.status_code != 200):
            raise ImprovMxError(r.status_code, payload)
        return payload

    def list_domains(self, q: Optional[str] = None, is_active: Optional[bool] = None, limit: int = 100, page: int = 1) -> Tuple[List[Domain], int]:
        params: Dict[str, Any] = {"limit": max(5, min(100, int(limit))), "page": max(1, int(page))}
        if q:
            params["q"] = q
        if is_active is not None:
            params["is_active"] = 1 if is_active else 0
        data = self._request("GET", "/domains", params=params)
        out: List[Domain] = []
        for d in data.get("domains", []) or []:
            out.append(Domain(
                domain=d.get("domain") or "",
                active=bool(d.get("active")),
                display=d.get("display") or (d.get("domain") or ""),
                added=d.get("added"),
                notification_email=d.get("notification_email"),
                whitelabel=d.get("whitelabel")
            ))
        return out, int(data.get("total") or len(out))

    def add_domain(self, domain: str, notification_email: Optional[str] = None, whitelabel: Optional[str] = None) -> Domain:
        body: Dict[str, Any] = {"domain": domain.strip()}
        if notification_email:
            body["notification_email"] = notification_email.strip()
        if whitelabel:
            body["whitelabel"] = whitelabel.strip()
        data = self._request("POST", "/domains", json_body=body)
        d = (data.get("domain") or {})
        return Domain(
            domain=d.get("domain") or domain.strip(),
            active=bool(d.get("active")),
            display=d.get("display") or (d.get("domain") or domain.strip()),
            added=d.get("added"),
            notification_email=d.get("notification_email"),
            whitelabel=d.get("whitelabel")
        )

    def delete_domain(self, domain: str) -> None:
        self._request("DELETE", f"/domains/{domain.strip()}")

    def list_aliases(self, domain: str, q: Optional[str] = None, limit: int = 100, page: int = 1) -> Tuple[List[Alias], int]:
        params: Dict[str, Any] = {"limit": max(5, min(100, int(limit))), "page": max(1, int(page))}
        if q:
            params["q"] = q
        data = self._request("GET", f"/domains/{domain.strip()}/aliases", params=params)
        out: List[Alias] = []
        for a in data.get("aliases", []) or []:
            out.append(Alias(
                id=int(a.get("id") or 0),
                alias=a.get("alias") or "",
                forward=a.get("forward") or "",
                created=a.get("created")
            ))
        return out, int(data.get("total") or len(out))

    def add_alias(self, domain: str, alias: str, forward: str) -> Alias:
        body = {"alias": alias.strip(), "forward": forward.strip()}
        data = self._request("POST", f"/domains/{domain.strip()}/aliases", json_body=body)
        a = (data.get("alias") or {})
        return Alias(
            id=int(a.get("id") or 0),
            alias=a.get("alias") or alias.strip(),
            forward=a.get("forward") or forward.strip(),
            created=a.get("created")
        )

    def update_alias(self, domain: str, alias_id: int, alias: str, forward: str) -> Alias:
        body = {"alias": alias.strip(), "forward": forward.strip()}
        data = self._request("PUT", f"/domains/{domain.strip()}/aliases/{int(alias_id)}", json_body=body)
        a = (data.get("alias") or {})
        return Alias(
            id=int(a.get("id") or alias_id),
            alias=a.get("alias") or alias.strip(),
            forward=a.get("forward") or forward.strip(),
            created=a.get("created")
        )

    def delete_alias(self, domain: str, alias_id: int) -> None:
        self._request("DELETE", f"/domains/{domain.strip()}/aliases/{int(alias_id)}")

    def bulk_aliases(self, domain: str, aliases: List[Dict[str, str]], behavior: str = "add") -> Dict[str, Any]:
        body = {"aliases": aliases, "behavior": behavior}
        return self._request("POST", f"/domains/{domain.strip()}/aliases/bulk", json_body=body)
