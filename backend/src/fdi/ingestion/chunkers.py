"""Registered chunkers by name. Names encode parameters and are stored on every chunk."""
from fdi.ingestion import chunking, table_chunking

B0 = chunking.chunker_name(150, 30)
R1 = table_chunking.chunker_name(12, 150, 30, 1200)

CHUNKERS = {
    B0: lambda pages, title: chunking.fixed_word_chunks(pages, 150, 30),
    R1: lambda pages, title: table_chunking.table_aware_chunks(pages, title, 12, 150, 30, 1200),
}
