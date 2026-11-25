"""Small, dependency-free adapters for electronics distributor search APIs."""

import json
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


def _json_request(url: str, *, headers: dict | None = None, body: dict | None = None) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = Request(url, data=data, headers={"Accept": "application/json", **(headers or {})})
    try:
        with urlopen(request, timeout=12) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        # Keep upstream response bodies and credentials out of our API response/logs.
        raise RuntimeError(f"upstream returned HTTP {exc.code}") from exc
    except (URLError, TimeoutError) as exc:
        raise RuntimeError("upstream request failed") from exc


def _integer(value) -> int:
    try:
        # Mouser commonly returns values such as "1,234 In Stock".
        match = re.search(r"\d[\d,]*", str(value or 0))
        return max(0, int(match.group(0).replace(",", ""))) if match else 0
    except (TypeError, ValueError):
        return 0


def search_mouser(part_number: str) -> list[dict]:
    api_key = os.environ.get("MOUSER_API_KEY")
    if not api_key:
        raise RuntimeError("not configured")
    payload = _json_request(
        f"https://api.mouser.com/api/v1/search/keyword?apiKey={quote(api_key)}",
        headers={"Content-Type": "application/json"},
        body={"SearchByKeywordRequest": {"keyword": part_number, "records": 5, "startingRecord": 0}},
    )
    parts = payload.get("SearchResults", {}).get("Parts", []) or []
    return [
        {
            "distributor": "Mouser",
            "part_number": part.get("ManufacturerPartNumber") or part_number,
            "manufacturer": part.get("Manufacturer") or "",
            "description": part.get("Description") or "",
            "stock": _integer(part.get("Availability")),
            "url": part.get("ProductDetailUrl") or "",
        }
        for part in parts
    ]


def search_digikey(part_number: str) -> list[dict]:
    client_id = os.environ.get("DIGIKEY_CLIENT_ID")
    access_token = _digikey_token(client_id)
    if not client_id or not access_token:
        raise RuntimeError("not configured")
    payload = _json_request(
        "https://api.digikey.com/products/v4/search/keyword",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
            "X-DIGIKEY-Client-Id": client_id,
            "X-DIGIKEY-Locale-Site": "US",
            "X-DIGIKEY-Locale-Language": "en",
            "X-DIGIKEY-Locale-Currency": "USD",
        },
        body={"Keywords": part_number, "Limit": 5, "Offset": 0},
    )
    products = payload.get("Products", []) or payload.get("products", []) or []
    offers = []
    for product in products:
        manufacturer = product.get("Manufacturer") or {}
        description = product.get("Description") or {}
        offers.append({
            "distributor": "DigiKey",
            "part_number": product.get("ManufacturerProductNumber") or part_number,
            "manufacturer": manufacturer.get("Name", "") if isinstance(manufacturer, dict) else str(manufacturer),
            "description": description.get("ProductDescription", "") if isinstance(description, dict) else str(description),
            "stock": _integer(product.get("QuantityAvailable")),
            "url": product.get("ProductUrl") or "",
        })
    return offers


_token_cache = {"value": "", "expires": 0.0}
_token_lock = threading.Lock()


def _digikey_token(client_id: str | None) -> str | None:
    """Use a supplied bearer token or obtain/cache one with client credentials."""
    supplied = os.environ.get("DIGIKEY_ACCESS_TOKEN")
    if supplied:
        return supplied
    client_secret = os.environ.get("DIGIKEY_CLIENT_SECRET")
    if not client_id or not client_secret:
        return None
    with _token_lock:
        if _token_cache["value"] and _token_cache["expires"] > time.time() + 30:
            return _token_cache["value"]
        request = Request(
            "https://api.digikey.com/v1/oauth2/token",
            data=urlencode({
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "client_credentials",
            }).encode("utf-8"),
            headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
        )
        try:
            with urlopen(request, timeout=12) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError) as exc:
            raise RuntimeError("authentication failed") from exc
        token = payload.get("access_token")
        if not token:
            raise RuntimeError("authentication failed")
        _token_cache.update(value=token, expires=time.time() + int(payload.get("expires_in", 600)))
        return token


PROVIDERS = {"mouser": search_mouser, "digikey": search_digikey}


def search_bom(items: list[dict], providers: list[str]) -> tuple[list[dict], dict]:
    """Search requested providers concurrently and preserve every BOM row."""
    searches = {}
    results = [{**item, "offers": [], "stock": 0} for item in items]
    errors: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=min(10, max(1, len(items) * len(providers)))) as pool:
        for index, item in enumerate(items):
            for provider in providers:
                searches[pool.submit(PROVIDERS[provider], item["part_number"])] = (index, provider)
        for future in as_completed(searches):
            index, provider = searches[future]
            try:
                offers = future.result()
                # Exact manufacturer part matches are preferred when the API supplies them.
                wanted = items[index]["part_number"].casefold()
                exact = [o for o in offers if o["part_number"].casefold() == wanted]
                results[index]["offers"].extend(exact or offers[:1])
            except RuntimeError as exc:
                errors[provider] = str(exc)
    for result in results:
        result["stock"] = sum(offer["stock"] for offer in result["offers"])
        result["in_stock"] = result["stock"] > 0
    return results, errors
