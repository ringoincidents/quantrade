import csv
import hashlib
import tempfile
import unittest
from pathlib import Path
from vault import connect,register_dataset,ingest_csv,snapshot
from private_backup import pack,verify,restore

class BackupTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.raw=self.root/"raw";self.raw.mkdir(mode=0o700)
        self.idx=self.root/"source.sqlite"
        self.db=connect(self.idx);self.addCleanup(self.db.close)
        register_dataset(self.db,"DEMO","DEMO","SyntheticTestProvider","USD","fixture")
        self.load("a",100,"2020-01-02T21:00:00Z")
        self.load("b",105,"2020-01-03T21:00:00Z")
        self.dest=self.root/"backup"
    def load(self,name,value,at):
        p=self.root/(name+".csv")
        with p.open("w",newline="") as f:
            w=csv.writer(f);w.writerow(["session","open","high","low","close","volume","first_available_at_utc"])
            w.writerow(["2020-01-02",value,value+1,value-1,value,10,at])
        raw=p.read_bytes();digest=hashlib.sha256(raw).hexdigest()
        (self.raw/(digest+".csv")).write_bytes(raw)
        ingest_csv(self.db,p,dataset_id="DEMO",source_uri="fixture:test",usage_rights_confirmed=True,availability_verified=True)
    def pack(self):
        return pack(self.idx,self.raw,self.dest,rights_confirmed=True)
    def test_roundtrip_revisions(self):
        p=self.pack();self.assertEqual(p["counts"],{"datasets":1,"batches":2,"bars":2})
        h=p["manifest_sha256"];self.assertEqual(verify(self.dest,h)["state"],"VERIFIED")
        target=self.root/"restored";self.assertEqual(restore(self.dest,target,h,rights_confirmed=True)["state"],"RESTORED")
        db=connect(target/"vault.sqlite")
        try:
            for t in ("2020-01-02T22:00:00Z","2020-01-04T00:00:00Z"):
                self.assertEqual(snapshot(db,"DEMO",t),snapshot(self.db,"DEMO",t))
            self.assertEqual(db.execute("SELECT * FROM batches ORDER BY sha256").fetchall(),self.db.execute("SELECT * FROM batches ORDER BY sha256").fetchall())
        finally:db.close()
    def test_no_rights(self):
        with self.assertRaisesRegex(ValueError,"BACKUP_RIGHTS_UNCONFIRMED"):pack(self.idx,self.raw,self.dest)
        self.assertFalse(self.dest.exists())
    def test_missing_raw(self):
        next(self.raw.iterdir()).unlink()
        with self.assertRaisesRegex(ValueError,"FILE_UNAVAILABLE"):self.pack()
        self.assertFalse((self.dest/"manifest.json").exists())
    def test_raw_corruption(self):
        h=self.pack()["manifest_sha256"]
        next((self.dest/"raw").iterdir()).write_bytes(b"corrupt")
        with self.assertRaisesRegex(ValueError,"RAW_HASH_MISMATCH"):restore(self.dest,self.root/"restore",h,rights_confirmed=True)
        self.assertFalse((self.root/"restore").exists())
    def test_index_corruption(self):
        h=self.pack()["manifest_sha256"]
        (self.dest/"vault.sqlite").write_bytes(b"corrupt")
        with self.assertRaisesRegex(ValueError,"INDEX_HASH_MISMATCH"):verify(self.dest,h)
    def test_manifest_hash_required(self):
        self.pack()
        with self.assertRaisesRegex(ValueError,"MANIFEST_HASH_REQUIRED"):verify(self.dest,None)
        with self.assertRaisesRegex(ValueError,"MANIFEST_HASH_MISMATCH"):verify(self.dest,"0"*64)
    def test_no_overwrite(self):
        h=self.pack()["manifest_sha256"]
        with self.assertRaises(FileExistsError):self.pack()
        target=self.root/"existing";target.mkdir(mode=0o700)
        with self.assertRaises(FileExistsError):restore(self.dest,target,h,rights_confirmed=True)
    def test_index_raw_disagreement(self):
        with self.db:self.db.execute("UPDATE bars SET close=close+0.1")
        with self.assertRaisesRegex(ValueError,"INDEX_RAW_MISMATCH"):self.pack()
    def test_missing_index_row(self):
        with self.db:self.db.execute("DELETE FROM bars WHERE close=100")
        with self.assertRaisesRegex(ValueError,"INDEX_ROWS_MISSING"):self.pack()
    def test_repository_path_rejected(self):
        repo=self.root/"repo";repo.mkdir(mode=0o700);(repo/".git").mkdir()
        with self.assertRaisesRegex(ValueError,"REPOSITORY_PATH_FORBIDDEN"):pack(self.idx,self.raw,repo/"backup",rights_confirmed=True)
    def test_restore_rights(self):
        h=self.pack()["manifest_sha256"]
        with self.assertRaisesRegex(ValueError,"RESTORE_RIGHTS_UNCONFIRMED"):restore(self.dest,self.root/"restore",h)
    def test_sidecar_rejected(self):
        h=self.pack()["manifest_sha256"];(self.dest/"vault.sqlite-wal").write_bytes(b"")
        with self.assertRaisesRegex(ValueError,"PACKAGE_FILE_SET_MISMATCH"):verify(self.dest,h)
