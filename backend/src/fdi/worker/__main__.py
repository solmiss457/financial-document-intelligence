"""Run the ingestion worker: python -m fdi.worker [--once] [--drain]."""
import argparse
import logging
import os
import socket
import time
from uuid import uuid4
from fdi.db.config import dsn
from fdi.db.session import create_pool
from fdi.storage import LocalStorage
from fdi.worker.jobs import Settings, run_once


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--once', action='store_true', help='process at most one job')
    parser.add_argument('--drain', action='store_true', help='exit when no job is claimable')
    parser.add_argument('--poll-seconds', type=float, default=5.0)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
    from fdi.ingestion.embedding import SentenceTransformerEmbedder
    embedder = SentenceTransformerEmbedder()
    worker_id = f'{socket.gethostname()}:{os.getpid()}:{uuid4().hex[:8]}'
    pool = create_pool(dsn(role='worker'), max_size=2, expected_role='fdi_worker')
    try:
        while True:
            outcome = run_once(pool, worker_id, LocalStorage(), embedder, Settings())
            if args.once or (outcome is None and args.drain):
                break
            if outcome is None:
                time.sleep(args.poll_seconds)
    finally:
        pool.close()


if __name__ == '__main__':
    main()
