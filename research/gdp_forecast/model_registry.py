"""Research-only model registry. No production promotion API."""
from forecast_ledger import append, read
MODELS=("SPF","IAR","Persistence","QT mean","QT median4","QT AR1 ridge","QT blend")

def register(db,name,version,code_sha,description):
    if name not in MODELS or not version or not description:
        raise ValueError("Unknown model or missing metadata")
    if len(code_sha)!=40 or any(c not in "0123456789abcdef" for c in code_sha):
        raise ValueError("Git commit required")
    return append(db,"model_definition",dict(name=name,version=version,code_sha=code_sha,description=description,status="RESEARCH_ONLY"))

def lookup(db,key):
    return read(db,key,"model_definition")
