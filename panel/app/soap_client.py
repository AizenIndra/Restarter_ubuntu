"""AzerothCore SOAP client (executeCommand)."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any
from xml.sax.saxutils import escape

import requests
from requests.auth import HTTPBasicAuth


class SOAPClient:
    def __init__(self, config: dict[str, Any]) -> None:
        self.cfg = config["soap"]

    @property
    def url(self) -> str:
        return f"http://{self.cfg['host']}:{int(self.cfg['port'])}/"

    def execute(self, command: str, timeout: float = 15.0) -> tuple[bool, str]:
        body = f"""<?xml version="1.0" encoding="utf-8"?>
<SOAP-ENV:Envelope
 xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/"
 xmlns:ns1="urn:AC">
  <SOAP-ENV:Body>
    <ns1:executeCommand>
      <command>{escape(command)}</command>
    </ns1:executeCommand>
  </SOAP-ENV:Body>
</SOAP-ENV:Envelope>"""
        try:
            resp = requests.post(
                self.url,
                data=body.encode("utf-8"),
                headers={"Content-Type": "text/xml; charset=utf-8"},
                auth=HTTPBasicAuth(self.cfg.get("username", ""), self.cfg.get("password", "")),
                timeout=timeout,
            )
        except Exception as exc:  # noqa: BLE001
            return False, f"SOAP request failed: {exc}"

        text = resp.text or ""
        if resp.status_code != 200:
            return False, f"SOAP HTTP {resp.status_code}: {text[:500]}"

        result = self._extract_result(text)
        if result is None:
            return False, f"SOAP parse error: {text[:500]}"
        return True, result.strip() or "(empty SOAP response)"

    @staticmethod
    def _extract_result(xml_text: str) -> str | None:
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            # fallback: strip tags roughly
            cleaned = re.sub(r"<[^>]+>", " ", xml_text)
            return cleaned.strip() or None

        # fault
        for fault in root.iter():
            if fault.tag.endswith("faultstring") and fault.text:
                return f"SOAP fault: {fault.text}"

        for node in root.iter():
            if node.tag.endswith("result") and node.text is not None:
                return node.text
            if node.tag.endswith("executeCommandResponse"):
                # nested result
                for child in node:
                    if child.tag.endswith("result") and child.text is not None:
                        return child.text
        return xml_text
