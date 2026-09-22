"""Download one consistent public snapshot, with checksums and atomic transfers."""
import hashlib, json, re, os
from pathlib import Path
from datetime import datetime, timezone
import requests
ROOT=Path(__file__).resolve().parent.parent
RAW=ROOT/"data/raw"
INDEX="https://insideairbnb.com/get-the-data/"
def main():
    r=requests.get(INDEX,timeout=45);r.raise_for_status()
    urls=set(re.findall(r'https?://data\.insideairbnb\.com/australia/[^/]+/sydney/\d{4}-\d{2}-\d{2}/(?:data|visualisations)/[\w.\-]+',r.text))
    groups={}
    for u in urls:
        snap=u.split("/sydney/")[1].split("/")[0]
        groups.setdefault(snap,{})[u.rsplit("/",1)[1]]=u
    wanted=["listings.csv.gz","calendar.csv.gz","reviews.csv.gz","neighbourhoods.geojson"]
    snaps=sorted(k for k,v in groups.items() if all(f in v for f in wanted))
    if not snaps: raise RuntimeError("No complete Sydney snapshot found")
    snap=snaps[-1];RAW.mkdir(parents=True,exist_ok=True)
    records=[]
    for name in wanted:
        url=groups[snap][name]; dest=RAW/name
        if dest.exists(): raise FileExistsError(f"{dest} exists. Preserve old files before downloading a new snapshot.")
        print("Downloading",url,flush=True)
        resp=requests.get(url,stream=True,timeout=(30,180));resp.raise_for_status()
        partial=dest.with_suffix(dest.suffix+".partial")
        with partial.open("wb") as f:
            for chunk in resp.iter_content(1024*1024): f.write(chunk)
        os.replace(partial,dest)
        h=hashlib.sha256()
        with dest.open("rb") as f:
            for chunk in iter(lambda:f.read(1024*1024),b""):h.update(chunk)
        records.append({"file":name,"url":url,"bytes":dest.stat().st_size,"sha256":h.hexdigest()})
    manifest={"snapshot":snap,"index_url":INDEX,"recorded_at":datetime.now(timezone.utc).isoformat(),
              "license":"CC BY 4.0; verify upstream terms when redistributing","files":records}
    (RAW/"manifest.json").write_text(json.dumps(manifest,indent=2))
    print("Manifest written",snap)
if __name__=="__main__":main()
