import base64
import binascii

import httpx

LEGISCAN_BASE = "https://api.legiscan.com/"
LEGISCAN_USER_AGENT = "legilens-worker/1.0 (+https://github.com/EMSwank/legilens)"

class LegiScanClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        # Datasets can be 20MB+ over slow links; 60s was timing out and burning
        # an API query per retry. Connect stays short to fail fast on network drops.
        self._http = httpx.AsyncClient(
            base_url=LEGISCAN_BASE,
            timeout=httpx.Timeout(connect=10.0, read=300.0, write=30.0, pool=10.0),
            headers={"User-Agent": LEGISCAN_USER_AGENT},
        )

    async def get_dataset_list(self, state: str | None = None) -> list[dict]:
        """Returns sessions with their change hashes. Pass state="CO" to get
        only Colorado sessions (server-side filter) — the response payload has
        no state_abbr field, only state_id, so client-side filtering by abbr
        is impossible without a fragile state_id map.
        """
        params: dict[str, str] = {"key": self.api_key, "op": "getDatasetList"}
        if state is not None:
            params["state"] = state
        resp = await self._http.get("/", params=params)
        resp.raise_for_status()
        payload = resp.json()
        if payload.get("status") != "OK":
            raise ValueError(f"getDatasetList returned non-OK status: {payload!r}")
        return payload.get("datasetlist", [])

    async def get_dataset(self, session_id: int, access_key: str) -> bytes:
        """Downloads a full session dataset as a zip.

        LegiScan getDataset requires both id (session_id) and access_key, and returns the zip
        base64-encoded inside a JSON envelope: {"status":"OK","dataset":{"zip":"<base64>", ...}}.
        """
        resp = await self._http.get(
            "/",
            params={"key": self.api_key, "op": "getDataset", "id": session_id, "access_key": access_key},
        )
        resp.raise_for_status()
        payload = resp.json()
        if payload.get("status") != "OK":
            raise ValueError(f"getDataset returned non-OK status: {payload!r}")
        encoded = payload.get("dataset", {}).get("zip")
        if not encoded:
            raise ValueError(f"getDataset response missing dataset.zip: {payload!r}")
        try:
            zip_bytes = base64.b64decode(encoded)
        except binascii.Error as exc:
            raise ValueError(f"getDataset base64 decode failed: {exc}") from exc
        if not zip_bytes.startswith(b"PK"):
            raise ValueError(f"getDataset decoded bytes are not a zip: {zip_bytes[:200]!r}")
        return zip_bytes

    async def get_bill_text(self, bill_id: int) -> str | None:
        """Fetches individual bill text. Phase 3 Pro API calls only — not used in Phase 1."""
        resp = await self._http.get("/", params={"key": self.api_key, "op": "getBill", "id": bill_id})
        resp.raise_for_status()
        texts = resp.json().get("bill", {}).get("texts", [])
        if not texts:
            return None
        return texts[-1].get("doc")

    async def close(self):
        await self._http.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
