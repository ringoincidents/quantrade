"""Explicit offline archive or bounded official HTTPS collection; no PIT certification."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import build_opener, HTTPRedirectHandler, Request
from urllib.parse import urlsplit

MAX_BYTES=8*1024*1024
HOST="www.philadelphiafed.org"
class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        raise ValueError("Redirect refused")

def check_url(url):
    p=urlsplit(url)
    if p.scheme!="https" or p.netloc!=HOST or not p.path.lower().startswith("/-/media/"):
        raise ValueError("Unapproved source URL")

def archive(raw,url,directory):
    check_url(url)
    if not raw or len(raw)>MAX_BYTES: raise ValueError("Invalid source size")
    root=Path(directory); root.mkdir(mode=0o700,parents=True,exist_ok=True)
    digest=hashlib.sha256(raw).hexdigest()
    path=root/digest
    try:
        with path.open("xb") as f: f.write(raw)
    except FileExistsError:
        if path.read_bytes()!=raw: raise ValueError("Existing evidence mismatch")
    manifest={"sha256":digest,"source_url":url,"captured_at":datetime.now(timezone.utc).isoformat(),"original_public_at":None,"status":"COLLECTOR_CAPTURE_ONLY"}
    return manifest

def collect(url,directory):
    check_url(url)
    with build_opener(NoRedirect()).open(Request(url,headers={"User-Agent":"QuanTrade research"}),timeout=20) as response:
        raw=response.read(MAX_BYTES+1)
    return archive(raw,url,directory)
