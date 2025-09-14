# src/jobs.py
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import text
from typing import Callable, Optional, List

log = logging.getLogger("jobs")

def start_scheduler(engine, embed_text: Optional[Callable[[str], List[float]]]):
    if not embed_text:
        log.info("Scheduler: embeddings disabled; not starting.")
        return
    sched = BackgroundScheduler(timezone="UTC")

    def backfill_embeddings():
        try:
            with engine.begin() as conn:
                rows = conn.execute(text("""
                    SELECT id, title, text FROM documents
                    WHERE embedding_vec IS NULL
                    ORDER BY id DESC LIMIT 50
                """)).mappings().all()
            if not rows: return
            for r in rows:
                vec = embed_text(f"{r['title'] or ''}\n\n{r['text'] or ''}")
                if not vec: continue
                with engine.begin() as conn:
                    conn.execute(text("""
                        UPDATE documents SET embedding = :e, embedding_vec = :e WHERE id = :id
                    """), {"e": vec, "id": r["id"]})
            log.info("Backfilled %d embeddings", len(rows))
        except Exception as e:
            log.exception("Backfill failed: %s", e)

    # every 5 minutes (tweak as you like)
    sched.add_job(backfill_embeddings, "interval", minutes=5, id="emb_backfill", max_instances=1, coalesce=True)
    sched.start()
    log.info("Scheduler started.")

