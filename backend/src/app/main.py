"""
FastAPI application: all routes + WebSocket endpoint.
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.build import service as svc
from app.build.events import manager as ws_manager
from app.build.models import (
    AnswerResponse,
    BuildRequest,
    BuildResponse,
    QuestionRequest,
)
from app.build.worker import run_build
from app.db.neo4j import close_driver, get_driver
from app.db.schema import create_schema
from app.qa.agent import answer_question

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up – creating Neo4j schema…")
    driver = await get_driver()
    await create_schema(driver)
    logger.info("Schema ready.")
    yield
    await close_driver()


app = FastAPI(title="WikiGraphRAG API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ──────────────────────────────────────────────────────────────────────────────
# Build endpoints
# ──────────────────────────────────────────────────────────────────────────────

@app.post("/api/builds", response_model=BuildResponse, status_code=201)
async def create_build(req: BuildRequest):
    build_id = svc.make_build_id()
    driver = await get_driver()

    # Persist Build node before starting worker
    await svc.init_build_node(driver, build_id, req)

    # Launch async build task
    task = asyncio.create_task(run_build(build_id, req.topic, req.max_pages, req.max_depth))
    svc.register_build(build_id, task)

    return BuildResponse(build_id=build_id, status="RUNNING")


@app.get("/api/builds/{build_id}")
async def get_build(build_id: str):
    driver = await get_driver()
    build = await svc.get_build(driver, build_id)
    if build is None:
        raise HTTPException(status_code=404, detail="Build not found")
    return build


@app.post("/api/builds/{build_id}/stop")
async def stop_build(build_id: str):
    svc.cancel_build(build_id)
    return {"status": "stopping", "build_id": build_id}


@app.get("/api/builds/{build_id}/logs")
async def get_build_logs(build_id: str):
    driver = await get_driver()
    logs = await svc.get_build_logs(driver, build_id)
    return {"logs": logs}


# ──────────────────────────────────────────────────────────────────────────────
# Graph snapshot
# ──────────────────────────────────────────────────────────────────────────────

@app.get("/api/builds/{build_id}/graph")
async def get_graph(
    build_id: str,
    center_entity_id: str | None = None,
    depth: int = 2,
    limit: int = 200,
):
    driver = await get_driver()
    async with driver.session() as s:
        if center_entity_id:
            # Neighborhood around a specific entity
            # Collect all neighbor entities, then unwind and fetch their edges.
            # We do NOT filter edges to the in-set here; the frontend ignores
            # edges whose endpoints aren't present in the node set.
            result = await s.run(
                f"""
                MATCH (center:Entity {{id: $cid}})-[:RELATED*0..{depth}]-(neighbor:Entity)
                WITH collect(DISTINCT neighbor) + [center] AS ents
                UNWIND ents AS e
                WITH e LIMIT $limit
                OPTIONAL MATCH (e)-[r:RELATED]->(e2:Entity)
                RETURN collect(DISTINCT {{id: e.id, label: e.name, type: e.type}}) AS nodes,
                       collect(DISTINCT CASE WHEN r IS NOT NULL THEN {{
                           id: r.claim_id + '::rel',
                           source: e.id,
                           target: e2.id,
                           label: r.relation_type,
                           claim_id: r.claim_id,
                           confidence: r.confidence
                       }} END) AS edges
                """,
                cid=center_entity_id,
                limit=limit,
            )
        else:
            # Full graph snapshot for this build.
            # Entities are found via two paths (OR):
            #   1. Build→SourcePage→SourceChunk←MENTIONED_IN←Entity
            #   2. Build→SourcePage←FROM_PAGE←Claim←HAS_CLAIM←Entity
            result = await s.run(
                """
                MATCH (b:Build {id: $build_id})-[:HAS_PAGE]->(p:SourcePage)
                OPTIONAL MATCH (p)-[:HAS_CHUNK]->(ch:SourceChunk)<-[:MENTIONED_IN]-(e1:Entity)
                OPTIONAL MATCH (p)<-[:FROM_PAGE]-(cl:Claim)<-[:HAS_CLAIM]-(e3:Entity)
                WITH collect(DISTINCT e1) + collect(DISTINCT e3) AS all_ents
                UNWIND all_ents AS e
                WITH e WHERE e IS NOT NULL
                WITH DISTINCT e LIMIT $limit
                OPTIONAL MATCH (e)-[r:RELATED]->(e2:Entity)
                RETURN collect(DISTINCT {id: e.id, label: e.name, type: e.type}) AS nodes,
                       collect(DISTINCT CASE WHEN r IS NOT NULL THEN {
                           id: r.claim_id + '::rel',
                           source: e.id,
                           target: e2.id,
                           label: r.relation_type,
                           claim_id: r.claim_id,
                           confidence: r.confidence
                       } END) AS edges
                """,
                build_id=build_id,
                limit=limit,
            )
        rec = await result.single()
        if rec is None:
            return {"nodes": [], "edges": []}
        nodes = rec["nodes"] or []
        edges = [e for e in (rec["edges"] or []) if e is not None]
        return {"nodes": nodes, "edges": edges}


# ──────────────────────────────────────────────────────────────────────────────
# Entity detail
# ──────────────────────────────────────────────────────────────────────────────

@app.get("/api/builds/{build_id}/entity/{entity_id}")
async def get_entity(build_id: str, entity_id: str):
    driver = await get_driver()
    async with driver.session() as s:
        result = await s.run(
            """
            MATCH (e:Entity {id: $eid})
            OPTIONAL MATCH (e)-[:HAS_CLAIM]->(cl:Claim)
            OPTIONAL MATCH (cl)-[:SUPPORTED_BY]->(ch:SourceChunk)
            OPTIONAL MATCH (ch)<-[:HAS_CHUNK]-(p:SourcePage)
            RETURN e {.id, .name, .canonical_name, .type, .description} AS entity,
                   collect(DISTINCT {
                     claim_id: cl.id,
                     predicate: cl.predicate,
                     object_text: cl.object_text,
                     confidence: cl.confidence,
                     chunk_id: ch.id,
                     snippet: left(ch.text, 250),
                     section: ch.section,
                     page_title: p.title,
                     url: p.url
                   })[..10] AS claims
            LIMIT 1
            """,
            eid=entity_id,
        )
        rec = await result.single()
        if rec is None:
            raise HTTPException(status_code=404, detail="Entity not found")

        # Also get RELATED entities
        rel_result = await s.run(
            """
            MATCH (e:Entity {id: $eid})-[r:RELATED]->(e2:Entity)
            RETURN e2.name AS name, e2.id AS id, r.relation_type AS rel_type,
                   r.confidence AS confidence
            LIMIT 20
            """,
            eid=entity_id,
        )
        related = await rel_result.data()
        return {
            "entity": dict(rec["entity"]),
            "claims": [c for c in rec["claims"] if c.get("claim_id")],
            "related": related,
        }


# ──────────────────────────────────────────────────────────────────────────────
# Q&A
# ──────────────────────────────────────────────────────────────────────────────

@app.post("/api/builds/{build_id}/ask", response_model=AnswerResponse)
async def ask(build_id: str, req: QuestionRequest):
    driver = await get_driver()
    build = await svc.get_build(driver, build_id)
    if build is None:
        raise HTTPException(status_code=404, detail="Build not found")
    return await answer_question(driver, build_id, req.question)


# ──────────────────────────────────────────────────────────────────────────────
# WebSocket
# ──────────────────────────────────────────────────────────────────────────────

@app.websocket("/ws/build/{build_id}")
async def websocket_endpoint(websocket: WebSocket, build_id: str):
    await ws_manager.connect(build_id, websocket)
    try:
        # Keep connection open; events are pushed by the build worker
        async for _ in websocket.iter_text():
            pass  # ignore any client messages (e.g. pings)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        ws_manager.disconnect(build_id, websocket)
