"""GitHub Releases updater for the portable Windows executable."""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from urllib.request import Request, urlopen

VERSION = "0.3.0"
DEFAULT_REPOSITORY = "GuelBDev/OpenShark"
SETTINGS = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "OpenShark" / "updates.json"


def repository(value):
    value = value.strip().removeprefix("https://github.com/").rstrip("/")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", value):
        raise ValueError("Informe github.com/usuario/repositorio")
    return value


def saved_repository():
    try:
        return repository(json.loads(SETTINGS.read_text(encoding="utf-8"))["repository"])
    except (OSError, ValueError, KeyError):
        return DEFAULT_REPOSITORY


def version(value):
    if not re.fullmatch(r"v?\d+\.\d+\.\d+", value):
        raise ValueError("A release precisa de uma tag vMAJOR.MINOR.PATCH")
    return tuple(int(x) for x in value.lstrip("v").split("."))


def check(value):
    repo = repository(value)
    request = Request(f"https://api.github.com/repos/{repo}/releases/latest",
                      headers={"Accept": "application/vnd.github+json", "User-Agent": "OpenShark/"+VERSION})
    with urlopen(request, timeout=15) as response:
        release = json.load(response)
    SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS.write_text(json.dumps({"repository": repo}), encoding="utf-8")
    if version(release["tag_name"]) <= version(VERSION):
        return None
    asset = next((a for a in release.get("assets", []) if a["name"].lower() == "openshark.exe"), None)
    if not asset:
        raise ValueError("A release não contém OpenShark.exe")
    expected = f"https://github.com/{repo}/releases/download/"
    if not asset.get("browser_download_url", "").startswith(expected):
        raise ValueError("Endereço de download inválido")
    digest = asset.get("digest") or ""
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
        raise ValueError("A release não informa o SHA-256 do executável")
    return {"tag": release["tag_name"], "url": asset["browser_download_url"],
            "sha256": digest[7:], "size": asset.get("size", 0)}


def download(release):
    folder = Path(tempfile.mkdtemp(prefix="OpenShark-update-"))
    target = folder / "OpenShark.exe"
    digest = hashlib.sha256()
    total = 0
    with urlopen(Request(release["url"], headers={"User-Agent": "OpenShark/"+VERSION}), timeout=30) as response, target.open("wb") as stream:
        while chunk := response.read(1024*1024):
            total += len(chunk)
            if total > 250*1024*1024:
                raise ValueError("Atualização excede o tamanho permitido")
            stream.write(chunk)
            digest.update(chunk)
    if digest.hexdigest() != release["sha256"] or (release["size"] and total != release["size"]):
        target.unlink(missing_ok=True)
        raise ValueError("Download incompleto ou SHA-256 divergente")
    return target


def install(staged):
    if not getattr(sys, "frozen", False):
        raise ValueError("Use o executável portátil para instalar atualizações")
    quote = lambda path: "'" + str(path).replace("'", "''") + "'"
    target = Path(sys.executable).resolve()
    backup = target.with_suffix(".exe.bak")
    # Windows keeps the running executable locked. The helper retries only this
    # explicit file and preserves a backup before replacing it.
    script = f"""
$ErrorActionPreference = 'Stop'
Wait-Process -Id {os.getpid()} -ErrorAction SilentlyContinue
$installed = $false
Copy-Item -LiteralPath {quote(target)} -Destination {quote(backup)} -Force
for ($attempt = 0; $attempt -lt 40; $attempt++) {{
  try {{
    Copy-Item -LiteralPath {quote(staged)} -Destination {quote(target)} -Force
    $installed = $true
    break
  }} catch {{ Start-Sleep -Milliseconds 500 }}
}}
if (-not $installed) {{
  if (Test-Path -LiteralPath {quote(backup)}) {{ Copy-Item -LiteralPath {quote(backup)} -Destination {quote(target)} -Force }}
}}
Start-Process -FilePath {quote(target)}
"""
    encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
    subprocess.Popen(["powershell.exe", "-NoProfile", "-WindowStyle", "Hidden", "-EncodedCommand", encoded],
                      creationflags=subprocess.CREATE_NO_WINDOW)
