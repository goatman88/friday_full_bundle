# src/app.py
from __future__ import annotations
import os, io, json, time, re, pathlib, typing as T

from fastapi import FastAPI, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# ---- storage paths
ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DATA.mkdir(parents=True, exist_ok=True)

# ---- optional deps (graceful import)
def _opt_import(name: str):
    try:
        return __import__(name)
    except Exception:
        return None

np = _opt_import("numpy")
joblib = _opt_import("joblib")
sklearn = _opt_import("sklearn")
faiss = _opt_import("faiss") or _opt_import("faiss_cpu")
boto3 = _opt_import("boto3")
sentence_transformers = _opt_import("sentence_transformers")

# -----------------------------
# Models for requests/responses
# -----------------------------
class ConfirmUploadReq(BaseModel):
    # Provide exactly ONE of these: raw text OR s3 URL
    raw: T.Optional[str] = Field(None, description="Raw text to add")
    s3: T.Optional[str] = Field(None, description="s3://bucket/key to fetch")
    collection: str = Field("default", description="Logical collection name")

class QueryReq(BaseModel):
    q: str = Field(..., description="User query")
    top_k: int = Field(5, ge=1, le=50)
    mode: str = Field("tfidf", description="tfidf | faiss")

# -----------------------------
# Mini helpers
# -----------------------------
def now_ts() -> int:
    return int(time.time())

def clean_text(s: str) -> str:
    s = s or ""
    return re.sub(r"\s+", " ", s).strip()

def load_env():
    load_dotenv()
    # AWS settings are optional; only needed if you’ll pull from S3
    return {
        "AWS_ACCESS_KEY_ID": os.getenv("AWS_ACCESS_KEY_ID"),
        "AWS_SECRET_ACCESS_KEY": os.getenv("AWS_SECRET_ACCESS_KEY"),
        "AWS_DEFAULT_REGION": os.getenv("AWS_DEFAULT_REGION") or "us-east-1",
    }

ENV = load_env()

# -----------------------------
# TF-IDF index (persisted)
# -----------------------------
class TfIdfIndex:
    VEC_PATH = DATA / "tfidf_vectorizer.joblib"
    CORPUS_PATH = DATA / "tfidf_corpus.json"

    def __init__(self) -> None:
        self.vectorizer = None
        self.doc_matrix = None
        self.docs: list[dict] = []  # [{text, meta}]
        self.ready = False
        if sklearn is None or joblib is None:
            return
        self._load_or_init()

    def _load_or_init(self):
        try:
            if self.VEC_PATH.exists() and self.CORPUS_PATH.exists():
                self.vectorizer = joblib.load(self.VEC_PATH)
                self.docs = json.loads(self.CORPUS_PATH.read_text("utf-8"))
                X = self.vectorizer.transform([d["text"] for d in self.docs])
                self.doc_matrix = X
                self.ready = True
            else:
                from sklearn.feature_extraction.text import TfidfVectorizer
                self.vectorizer = TfidfVectorizer(
                    max_features=50_000,
                    stop_words="english",
                )
                self.docs = []
                self.doc_matrix = None
                self.ready = True
        except Exception:
            self.ready = False

    def _fit_if_needed(self):
        if not self.docs:
            self.doc_matrix = None
            return
        X = self.vectorizer.fit_transform([d["text"] for d in self.docs])
        self.doc_matrix = X
        joblib.dump(self.vectorizer, self.VEC_PATH)
        self.CORPUS_PATH.write_text(json.dumps(self.docs, ensure_ascii=False), "utf-8")

    def add_doc(self, text: str, meta: dict):
        text = clean_text(text)
        if not text:
            return 0
        self.docs.append({"text": text, "meta": meta})
        # refit after every add (small scale); for big loads batch then fit once
        self._fit_if_needed()
        return 1

    def search(self, q: str, top_k: int = 5):
        if not self.ready or self.doc_matrix is None or self.doc_matrix.shape[0] == 0:
            return []
        q_vec = self.vectorizer.transform([q])
        # cosine on L2-normed tfidf is dot because sklearn normalizes by default
        scores = (self.doc_matrix @ q_vec.T).toarray().ravel()
        idx = scores.argsort()[::-1][:top_k]
        out = []
        for i in idx:
            out.append({
                "score": float(scores[i]),
                "text": self.docs[i]["text"][:500],
                "meta": self.docs[i]["meta"]
            })
        return out

# -----------------------------
# FAISS index (persisted)
# -----------------------------
class FaissIndex:
    INDEX_PATH = DATA / "faiss.index"
    META_PATH = DATA / "faiss_meta.json"

    def __init__(self) -> None:
        self.model = None
        self.index = None
        self.texts: list[str] = []
        self.metas: list[dict] = []
        self.ready = False
        if sentence_transformers is None or faiss is None or np is None:
            return
        self.model = sentence_transformers.SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        self.dim = 384
        self._load_or_init()

    def _load_or_init(self):
        try:
            if self.INDEX_PATH.exists() and self.META_PATH.exists():
                self.index = faiss.read_index(str(self.INDEX_PATH))
                meta = json.loads(self.META_PATH.read_text("utf-8"))
                self.texts = meta["texts"]
                self.metas = meta["metas"]
                self.ready = True
            else:
                self.index = faiss.IndexFlatIP(self.dim)  # dot-product (use normalized vectors)
                self.texts, self.metas = [], []
                self._persist()
                self.ready = True
        except Exception:
            self.ready = False

    def _persist(self):
        faiss.write_index(self.index, str(self.INDEX_PATH))
        self.META_PATH.write_text(json.dumps({"texts": self.texts, "metas": self.metas}, ensure_ascii=False), "utf-8")

    def _embed(self, texts: list[str]):
        embs = self.model.encode(texts, convert_to_numpy=True, show_progress_bar=False, normalize_embeddings=True)
        if embs.ndim == 1:
            embs = embs.reshape(1, -1)
        return embs.astype("float32")

    def add_doc(self, text: str, meta: dict):
        text = clean_text(text)
        if not text:
            return 0
        emb = self._embed([text])
        self.index.add(emb)
        self.texts.append(text)
        self.metas.append(meta)
        self._persist()
        return 1

    def search(self, q: str, top_k: int = 5):
        if not self.ready or self.index is None or self.index.ntotal == 0:
            return []
        qv = self._embed([q])
        D, I = self.index.search(qv, top_k)
        D = D[0]; I = I[0]
        out = []
        for score, idx in zip(D, I):
            if int(idx) < 0 or int(idx) >= len(self.texts):
                continue
            out.append({
                "score": float(score),
                "text": self.texts[int(idx)][:500],
                "meta": self.metas[int(idx)]
            })
        return out

# -----------------------------
# set up app + indexes
# -----------------------------
app = FastAPI(title="Friday RAG API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"]
)

TFIDF = TfIdfIndex()
FAISSX = FaissIndex()

# -----------------------------
# Routes
# -----------------------------
@app.get("/")
def root():
    return {"ok": True, "ts": now_ts(), "docs_tfidf": len(TFIDF.docs), "docs_faiss": len(FAISSX.texts)}

@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "ts": now_ts(),
        "indexes": {
            "tfidf": {"ready": TFIDF.ready, "docs": len(TFIDF.docs)},
            "faiss": {"ready": FAISSX.ready, "docs": len(FAISSX.texts)},
        }
    }

# Upload URL + PUT token are stubs (you’re uploading elsewhere or using S3)
@app.get("/api/rag/upload_url")
def get_upload_url():
    return {"message": "Use /api/rag/confirm_upload with { raw: <text> } or { s3: 's3://bucket/key' }"}

@app.put("/api/rag/upload_put/{token}")
def upload_put(token: str):
    return {"message": f"Stub PUT accepted for token={token}"}

@app.post("/api/rag/confirm_upload")
def confirm_upload(payload: ConfirmUploadReq = Body(...)):
    text = None
    meta = {"collection": payload.collection, "ts": now_ts()}

    if payload.raw:
        text = payload.raw

    elif payload.s3:
        if boto3 is None:
            return {"error": "boto3 not installed; cannot fetch from S3"}
        # parse s3://bucket/key
        m = re.match(r"^s3://([^/]+)/(.+)$", payload.s3.strip())
        if not m:
            return {"error": "Invalid S3 URI; expected s3://bucket/key"}
        bucket, key = m.group(1), m.group(2)
        s3 = boto3.client(
            "s3",
            aws_access_key_id=ENV["AWS_ACCESS_KEY_ID"],
            aws_secret_access_key=ENV["AWS_SECRET_ACCESS_KEY"],
            region_name=ENV["AWS_DEFAULT_REGION"],
        )
        obj = s3.get_object(Bucket=bucket, Key=key)
        raw = obj["Body"].read()
        try:
            text = raw.decode("utf-8", errors="ignore")
        except Exception:
            text = None
        meta.update({"source": "s3", "bucket": bucket, "key": key})

    else:
        return {"error": "Provide either 'raw' or 's3' in the request body."}

    if not text:
        return {"error": "Empty text."}

    # Add to both indexes (they’re independent)
    added_tfidf = TFIDF.add_doc(text, meta)
    added_faiss = FAISSX.add_doc(text, meta)

    return {"status": "ok", "added": {"tfidf": added_tfidf, "faiss": added_faiss}}

@app.post("/api/rag/query")
def query(payload: QueryReq = Body(...)):
    mode = (payload.mode or "tfidf").lower()
    if mode not in ("tfidf", "faiss"):
        mode = "tfidf"

    if mode == "faiss":
        hits = FAISSX.search(payload.q, top_k=payload.top_k)
    else:
        hits = TFIDF.search(payload.q, top_k=payload.top_k)

    if not hits:
        return {"answer": "No matches in index.", "hits": []}

    # very basic "answer"
    best = hits[0]["text"]
    return {"answer": best[:200], "hits": hits}





























































































