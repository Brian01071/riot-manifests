from utils import get_exe_version, download_manifest, save_file, setup_session
import json
import plistlib
import os
from multiprocessing.pool import ThreadPool
import subprocess

version_sets = ["BR1", "EUN1", "EUW1", "JP1", "KR", "LA1", "LA2", "ME1", "NA1", "OC1", "PBE1", "PH2", "RU", "SG2", "TH2", "TR1", "TW2", "VN2"]
session = setup_session()
pool = ThreadPool(8)

def update_versions(region):
    for OS in ["android", "ios", "macos", "windows"]:
        releases = session.get(f"https://sieve.services.riotcdn.net/api/v1/products/lol/version-sets/{region}?q[platform]={OS}", timeout=2)
        releases.raise_for_status()

        for release in json.loads(releases.content)["releases"]:
            artifact_type_id = release["release"]["labels"]["riot:artifact_type_id"]["values"][0]
            path = f'{"LoL" if OS in {"macos", "windows"} else "TFT"}/{region}/{OS}/{artifact_type_id}'
            if artifact_type_id == "lol-standalone-client":
                # "public-android-arm64-now-store" -> ""
                # "public-android-arm64-now-store-vn" -> "-vn"
                path += release["release"]["labels"]["buildtracker_config"]["values"][0].split("store")[-1]

            os.makedirs(path, exist_ok=True)
            save_file(f'{path}/{release["release"]["labels"]["riot:artifact_version_id"]["values"][0].split("+")[0]}.txt', release["download"]["url"])

pool.map(update_versions, version_sets, 1)

region_map = {"BR": "BR1", "EUNE": "EUN1", "EUW": "EUW1", "JP": "JP1", "KR": "KR", "LA1": "LA1", "LA2": "LA2", "ME1": "ME1", "NA": "NA1", "OC1": "OC1", "PH2": "PH2", "RU": "RU", "SG2": "SG2", "TH2": "TH2", "TR": "TR1", "TW2": "TW2", "VN2": "VN2", "PBE": "PBE1"}
os_map = {"win": "windows", "mac": "macos"}

client_releases = session.get("https://clientconfig.rpg.riotgames.com/api/v1/config/public?namespace=keystone.products.league_of_legends.patchlines", timeout=2)
client_releases.raise_for_status()

configurations = []
for patchline in json.loads(client_releases.content).values():
    for platform in patchline["platforms"]:
        for configuration in patchline["platforms"][platform]["configurations"]:
            configurations.append((region_map[configuration["id"]], platform, configuration["patch_url"]))

versions = []
os.makedirs("LoL/temp", exist_ok=True)
pool.starmap(download_manifest, {(configuration[2], "LoL/temp", session) for configuration in configurations}, 1)

for configuration in configurations:
    if configuration[1] == "mac":
        subprocess.check_call(["./ManifestDownloader.exe", f"LoL/temp/{configuration[2][-25:]}", "-f", "Contents/LoL/LeagueClient.app/Contents/Info.plist", "-o", "LoL/temp"], timeout=5)
        with open("LoL/temp/Contents/LoL/LeagueClient.app/Contents/Info.plist", "rb") as in_file:
            exe_version = f'{plistlib.load(in_file)["FileVersion"]}_{configuration[2][-25:-9]}'
    else: # windows
        subprocess.check_call(["./ManifestDownloader.exe", f"LoL/temp/{configuration[2][-25:]}", "-f", "LeagueClient.exe", "-o", "LoL/temp", "-t", "4"], timeout=10)
        try:
            exe_version = get_exe_version("LoL/temp/LeagueClient.exe")
        except ValueError:
            exe_version = configuration[2][-25:-9]
            print(exe_version)
    versions.append((configuration[0], os_map[configuration[1]], exe_version, configuration[2]))

for version in versions:
    path = f"LoL/{version[0]}/{version[1]}/league-client"
    os.makedirs(path, exist_ok=True)
    save_file(f"{path}/{version[2]}.txt", version[3])
