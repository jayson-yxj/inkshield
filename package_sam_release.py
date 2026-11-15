"""Package the verified onedir SAM release, retaining all dependency resources."""
from pathlib import Path
import hashlib, json, zipfile

ROOT=Path(__file__).resolve().parent
FOLDER=ROOT/'dist/inkshield-20261110-r2/Inkshield'
ARCHIVE=ROOT/'dist/inkshield-20261110-r2/隐映-Windows-x64-多层工作区CPU-GPU版-20261110-修订2.zip'

README=(ROOT/'WINDOWS使用说明.txt').read_text(encoding='utf-8')


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    if not (FOLDER/'Inkshield.exe').is_file(): raise RuntimeError('Verified release EXE missing')
    if ARCHIVE.exists(): raise RuntimeError('Refusing to replace a delivered ZIP')
    exe_sha=digest(FOLDER/'Inkshield.exe')
    from verify_sam_release_binding import release_binding
    binding=release_binding(FOLDER/'Inkshield.exe')
    matrices=[]
    for candidate in (ROOT/'runtime').glob('sam-frozen-matrix-*/evidence.json'):
        record=json.loads(candidate.read_text(encoding='utf-8'))
        if record.get('status')=='passed' and record.get('exe_sha256')==exe_sha and record.get('release_binding')==binding:
            matrices.append(str(candidate))
    legacy=[]
    for candidate in (ROOT/'runtime').glob('sam-legacy-*/acceptance.json'):
        record=json.loads(candidate.read_text(encoding='utf-8'))
        cleanup=candidate.parent/'cleanup.json'
        if record.get('exe_sha256')==exe_sha and record.get('release_binding')==binding and all(record.get(key) for key in ('identity','plate_segments','audio')) and cleanup.is_file() and all(json.loads(cleanup.read_text(encoding='utf-8')).values()):
            legacy.append(str(candidate))
    desktops=[]
    for candidate in (ROOT/'runtime').glob('sam-desktop-launch-*/evidence.json'):
        record=json.loads(candidate.read_text(encoding='utf-8'))
        if record.get('status')=='passed' and record.get('exe_sha256')==exe_sha and record.get('release_binding')==binding and record.get('cleanup') and all(record['cleanup'].values()):
            desktops.append(str(candidate))
    if not matrices or not legacy or not desktops:
        raise RuntimeError('Matching frozen matrix, legacy and actual desktop acceptance with cleanup are required before packaging')
    from verify_sam_bundle import main as verify_bundle
    verify_bundle()
    (FOLDER/'使用说明.txt').write_text(README,encoding='utf-8-sig')
    entries=[]
    for path in sorted(FOLDER.rglob('*')):
        if path.is_file() and path != FOLDER/'SHA256.json': entries.append({'path':path.relative_to(FOLDER).as_posix(),'bytes':path.stat().st_size,'sha256':digest(path)})
    manifest={'files':entries,'bytes':sum(entry['bytes'] for entry in entries),'exe_sha256':digest(FOLDER/'Inkshield.exe')}
    (FOLDER/'SHA256.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    with zipfile.ZipFile(ARCHIVE,'x',zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as archive:
        for path in sorted(FOLDER.rglob('*')):
            if path.is_file(): archive.write(path,'Inkshield/'+path.relative_to(FOLDER).as_posix())
    with zipfile.ZipFile(ARCHIVE) as archive:
        corrupt=archive.testzip()
        if corrupt: raise RuntimeError('ZIP corruption: '+corrupt)
        expected_names={'Inkshield/'+entry['path'] for entry in entries}|{'Inkshield/SHA256.json'}
        if len(archive.namelist()) != len(expected_names) or set(archive.namelist()) != expected_names:
            raise RuntimeError('ZIP entry set mismatch')
        for entry in entries:
            name='Inkshield/'+entry['path']
            if archive.getinfo(name).file_size != entry['bytes']: raise RuntimeError('Embedded size mismatch: '+name)
            with archive.open(name) as stream:
                if hashlib.file_digest(stream,'sha256').hexdigest()!=entry['sha256']: raise RuntimeError('Embedded SHA256 mismatch: '+name)
        with archive.open('Inkshield/SHA256.json') as stream:
            if hashlib.file_digest(stream,'sha256').hexdigest()!=digest(FOLDER/'SHA256.json'): raise RuntimeError('Embedded manifest mismatch')
    if release_binding(FOLDER/'Inkshield.exe') != binding: raise RuntimeError('Release binding changed during packaging')
    record={'release_binding':binding,'zip':str(ARCHIVE),'zip_bytes':ARCHIVE.stat().st_size,'zip_sha256':digest(ARCHIVE),'files':len(entries)+1,'uncompressed_bytes':manifest['bytes'],'exe_sha256':manifest['exe_sha256'],'frozen_matrix_evidence':matrices,'legacy_evidence':legacy,'desktop_evidence':desktops}
    (ROOT/'runtime/sam-release-package-20261110.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(record,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
