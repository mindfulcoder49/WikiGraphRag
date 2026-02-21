"""
Neo4j schema: constraints and indexes created at startup.
"""
from neo4j import AsyncDriver

_CONSTRAINTS = [
    "CREATE CONSTRAINT build_id IF NOT EXISTS FOR (b:Build) REQUIRE b.id IS UNIQUE",
    "CREATE CONSTRAINT source_page_id IF NOT EXISTS FOR (p:SourcePage) REQUIRE p.id IS UNIQUE",
    "CREATE CONSTRAINT source_chunk_id IF NOT EXISTS FOR (c:SourceChunk) REQUIRE c.id IS UNIQUE",
    "CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE",
    "CREATE CONSTRAINT claim_id IF NOT EXISTS FOR (cl:Claim) REQUIRE cl.id IS UNIQUE",
]

_INDEXES = [
    "CREATE INDEX entity_canonical_name IF NOT EXISTS FOR (e:Entity) ON (e.canonical_name)",
    "CREATE INDEX entity_name IF NOT EXISTS FOR (e:Entity) ON (e.name)",
    "CREATE INDEX chunk_page_id IF NOT EXISTS FOR (c:SourceChunk) ON (c.page_id)",
]

# TODO: Add fulltext index on SourceChunk.text for semantic fallback retrieval
# CREATE FULLTEXT INDEX chunk_text IF NOT EXISTS FOR (c:SourceChunk) ON EACH [c.text]


async def create_schema(driver: AsyncDriver) -> None:
    async with driver.session() as session:
        for stmt in _CONSTRAINTS:
            await session.run(stmt)
        for stmt in _INDEXES:
            await session.run(stmt)
