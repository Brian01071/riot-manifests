import ssl
from requests import Session
from requests.adapters import HTTPAdapter
import re
import hachoir.parser
import hachoir.metadata
from hachoir.stream import FileInputStream
from typing import Tuple
import os.path

class TLSAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs) -> None:
        ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        # ctx.minimum_version = ssl.TLSVersion.TLSv1_3
        # ctx.set_ciphers('DEFAULT@SECLEVEL=1')
        kwargs['ssl_context'] = ctx
        return super(TLSAdapter, self).init_poolmanager(*args, **kwargs)

def setup_session() -> Session:
    session = Session()
    session.headers = {
        "Accept": "application/json",
        "User-Agent": "lul"
    }
    session.mount('https://', TLSAdapter())

    return session

def get_lor_tokens(username, password, session=None) -> Tuple[str, str, str, str, str]:
    if session is None:
        session = setup_session()

    post_payload = {
        "client_id": "bacon-client",
        "nonce": "none",
        "response_type": "token id_token",
        "redirect_uri": "http://localhost/redirect",
        "scope": "account openid"
    }
    post_response = session.post("https://auth.riotgames.com/api/v1/authorization", json=post_payload, timeout=2)
    post_response.raise_for_status()

    put_payload = {
        "type": "auth",
        "username": username,
        "password": password
    }
    put_response = session.put("https://auth.riotgames.com/api/v1/authorization", json=put_payload, headers={"referer": "https://riotgames.com/"}, timeout=2)
    put_response.raise_for_status()
    access_token, id_token = re.search("access_token=(.*)&scope=.*id_token=(.*)&token_type=", put_response.content.decode()).groups()

    entitlements_token_response = session.post("https://entitlements.auth.riotgames.com/api/token/v1", json={"urn": "urn:entitlement:%"}, headers={"Authorization": f"Bearer {access_token}"}, timeout=1)
    entitlements_token_response.raise_for_status()
    entitlements_token = entitlements_token_response.json()["entitlements_token"]

    userinfo_response = session.get("https://auth.riotgames.com/userinfo", headers={"Authorization": f"Bearer {access_token}"}, timeout=1)
    userinfo_response.raise_for_status()
    userinfo = userinfo_response.content.decode()

    pas_token_response = session.put("https://riot-geo.pas.si.riotgames.com/pas/v1/product/bacon", json={"id_token": id_token}, headers={"Authorization": f"Bearer {access_token}"}, timeout=1)
    pas_token_response.raise_for_status()
    pas_token = pas_token_response.json()["token"]

    return (entitlements_token, access_token, id_token, userinfo, pas_token)

def get_exe_version(path):
    with FileInputStream(path) as stream:
        parser = hachoir.parser.guessParser(stream)
        metadata = hachoir.metadata.extractMetadata(parser)
        version = metadata.get("version")
    return version

def download_manifest(manifest_url, temp_path, session=None):
    if session is None:
        session = setup_session()

    manifest_path = f"{temp_path}/{manifest_url[-25:]}"
    if os.path.exists(manifest_path):
        return

    manifest = session.get(manifest_url, timeout=5)
    manifest.raise_for_status()

    with open(f"{manifest_path}.temp", "wb") as out_file:
        out_file.write(manifest.content)
    os.rename(f"{manifest_path}.temp", manifest_path)

# Because riot likes semantic versioning they will release a new version with
# exactly the same version number whenever they want, so there's a mechanism
# for saving multiple "same" versions
def save_file(file_path, data):
    if isinstance(data, str):
        data = data.encode()

    try:
        with open(file_path, "rb") as in_file:
            old_data = in_file.read()
    except:
        old_data = None

    path_part, extension = os.path.splitext(file_path)
    counter = 1

    while old_data is not None and old_data != data:
        counter += 1
        file_path = f"{path_part}__{counter}{extension}"
        try:
            with open(file_path, "rb") as in_file:
                old_data = in_file.read()
        except:
            old_data = None

    if old_data is None:
        with open(file_path, "wb") as out_file:
            out_file.write(data)
