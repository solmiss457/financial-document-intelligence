-- Each ingestion job names the chunker it runs, so B0 and R1 chunks can be built for the
-- same document version. Existing and default jobs use the B0 chunker.
SET LOCAL ROLE fdi_owner;
ALTER TABLE fdi.ingestion_jobs ADD COLUMN chunker text NOT NULL DEFAULT 'fixed_words_v1:150/30';
