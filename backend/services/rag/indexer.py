"""RAG indexer: chunks policy docs + medical guidelines → embeds → upserts to Pinecone."""
from __future__ import annotations

import json
import logging
import os
import uuid
from pathlib import Path

from pinecone import Pinecone, ServerlessSpec
from services.gemini_service import embed_text
from services.rag.namespaces import CLAIMS, MEDICAL, POLICY

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent.parent / "data"


def _get_index():
    api_key = os.environ.get("PINECONE_API_KEY")
    index_name = os.environ.get("PINECONE_INDEX_NAME", "plum-opd")
    if not api_key:
        raise RuntimeError("PINECONE_API_KEY env var not set")
    pc = Pinecone(api_key=api_key)

    # Create index if it doesn't exist
    existing = [i.name for i in pc.list_indexes()]
    if index_name not in existing:
        logger.info(f"Creating Pinecone index '{index_name}'...")
        pc.create_index(
            name=index_name,
            dimension=768,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )
        logger.info("Index created.")

    return pc.Index(index_name)


def _is_namespace_populated(index, namespace: str) -> bool:
    try:
        stats = index.describe_index_stats()
        ns_stats = stats.get("namespaces", {})
        count = ns_stats.get(namespace, {}).get("vector_count", 0)
        return count > 0
    except Exception:
        return False


def _upsert_chunks(index, chunks: list[dict], namespace: str, batch_size: int = 50):
    """Embed and upsert a list of {id, text, metadata} chunks."""
    vectors = []
    for chunk in chunks:
        try:
            embedding = embed_text(chunk["text"])
            vectors.append({
                "id": chunk["id"],
                "values": embedding,
                "metadata": {"text": chunk["text"], **chunk.get("metadata", {})},
            })
        except Exception as e:
            logger.warning(f"Failed to embed chunk {chunk['id']}: {e}")

    # Upsert in batches
    for i in range(0, len(vectors), batch_size):
        batch = vectors[i:i + batch_size]
        index.upsert(vectors=batch, namespace=namespace)
    logger.info(f"Upserted {len(vectors)} vectors to namespace '{namespace}'")


# ── Policy chunking ────────────────────────────────────────────────────────────

def _chunk_policy_terms() -> list[dict]:
    path = DATA_DIR / "policy_terms.json"
    if not path.exists():
        logger.warning("policy_terms.json not found")
        return []

    with open(path) as f:
        policy = json.load(f)

    chunks = []

    # Top-level metadata
    chunks.append({
        "id": "policy-overview",
        "text": f"Policy: {policy.get('policy_name')}. Policy ID: {policy.get('policy_id')}. Effective: {policy.get('effective_date')}.",
        "metadata": {"section": "overview", "source": "policy_terms"},
    })

    # Coverage details — one chunk per category
    coverage = policy.get("coverage_details", {})
    for cat, details in coverage.items():
        text = f"Coverage for {cat}: {json.dumps(details)}"
        chunks.append({
            "id": f"policy-coverage-{cat}",
            "text": text,
            "metadata": {"section": f"coverage_{cat}", "source": "policy_terms"},
        })

    # Waiting periods
    waiting = policy.get("waiting_periods", {})
    text = f"Waiting periods: {json.dumps(waiting)}"
    chunks.append({
        "id": "policy-waiting-periods",
        "text": text,
        "metadata": {"section": "waiting_periods", "source": "policy_terms"},
    })

    # Exclusions
    exclusions = policy.get("exclusions", [])
    chunks.append({
        "id": "policy-exclusions",
        "text": f"Excluded treatments/conditions: {', '.join(exclusions)}",
        "metadata": {"section": "exclusions", "source": "policy_terms"},
    })

    # Claim requirements
    reqs = policy.get("claim_requirements", {})
    chunks.append({
        "id": "policy-claim-requirements",
        "text": f"Claim requirements: {json.dumps(reqs)}",
        "metadata": {"section": "claim_requirements", "source": "policy_terms"},
    })

    # Network hospitals
    network = policy.get("network_hospitals", [])
    chunks.append({
        "id": "policy-network-hospitals",
        "text": f"Network hospitals (20% discount, cashless available): {', '.join(network)}",
        "metadata": {"section": "network_hospitals", "source": "policy_terms"},
    })

    return chunks


def _chunk_adjudication_rules() -> list[dict]:
    path = DATA_DIR / "adjudication_rules.md"
    if not path.exists():
        logger.warning("adjudication_rules.md not found")
        return []

    with open(path) as f:
        content = f.read()

    # Split by ## headings
    import re
    sections = re.split(r"\n## ", content)
    chunks = []
    for i, section in enumerate(sections):
        if not section.strip():
            continue
        title = section.split("\n")[0].strip("# ").strip()
        chunks.append({
            "id": f"rules-section-{i}",
            "text": section[:1200],  # cap at ~300 tokens
            "metadata": {"section": title, "source": "adjudication_rules"},
        })
    return chunks


# ── Medical guidelines chunking ────────────────────────────────────────────────

def _chunk_medical_guidelines() -> list[dict]:
    path = DATA_DIR / "medical_guidelines.json"
    if not path.exists():
        logger.warning("medical_guidelines.json not found")
        return []

    with open(path) as f:
        guidelines = json.load(f)

    chunks = []
    for entry in guidelines:
        diagnosis = entry.get("diagnosis", "")
        text = (
            f"Diagnosis: {diagnosis}. "
            f"Standard medicines: {', '.join(entry.get('standard_medicines', []))}. "
            f"Standard tests: {', '.join(entry.get('standard_tests', []))}. "
            f"Notes: {entry.get('notes', '')}"
        )
        chunks.append({
            "id": f"medical-{diagnosis.lower().replace(' ', '-')}",
            "text": text,
            "metadata": {"diagnosis": diagnosis, "source": "medical_guidelines"},
        })
    return chunks


# ── Seed claims chunking ───────────────────────────────────────────────────────

def _chunk_seed_claims() -> list[dict]:
    path = DATA_DIR / "seed_claims.json"
    if not path.exists():
        logger.warning("seed_claims.json not found")
        return []

    with open(path) as f:
        seed_claims = json.load(f)

    chunks = []
    for claim in seed_claims:
        text = (
            f"Past claim: {claim.get('claim_type')} claim, "
            f"₹{claim.get('amount')}, "
            f"diagnosis: {claim.get('diagnosis', 'N/A')}, "
            f"decision: {claim.get('decision')}, "
            f"reason: {claim.get('primary_reason', '')}"
        )
        chunks.append({
            "id": f"claim-seed-{claim.get('id', uuid.uuid4())}",
            "text": text,
            "metadata": {
                "decision": claim.get("decision"),
                "claim_type": claim.get("claim_type"),
                "amount": claim.get("amount"),
                "source": "seed_claims",
            },
        })
    return chunks


# ── Main entry point ───────────────────────────────────────────────────────────

async def ensure_indexed():
    """Ensure all namespaces are populated. Skips namespaces already populated."""
    index = _get_index()

    if not _is_namespace_populated(index, POLICY):
        logger.info("Indexing policy documents...")
        policy_chunks = _chunk_policy_terms() + _chunk_adjudication_rules()
        if policy_chunks:
            _upsert_chunks(index, policy_chunks, POLICY)
    else:
        logger.info(f"Namespace '{POLICY}' already populated, skipping.")

    if not _is_namespace_populated(index, MEDICAL):
        logger.info("Indexing medical guidelines...")
        medical_chunks = _chunk_medical_guidelines()
        if medical_chunks:
            _upsert_chunks(index, medical_chunks, MEDICAL)
    else:
        logger.info(f"Namespace '{MEDICAL}' already populated, skipping.")

    if not _is_namespace_populated(index, CLAIMS):
        logger.info("Indexing seed claims...")
        claim_chunks = _chunk_seed_claims()
        if claim_chunks:
            _upsert_chunks(index, claim_chunks, CLAIMS)
    else:
        logger.info(f"Namespace '{CLAIMS}' already populated, skipping.")


def upsert_claim_to_index(claim_id: str, claim_type: str, amount: int,
                           diagnosis: str, decision: str, primary_reason: str):
    """Add a newly adjudicated claim to the claims namespace."""
    try:
        index = _get_index()
        text = (
            f"Past claim: {claim_type} claim, ₹{amount}, "
            f"diagnosis: {diagnosis}, decision: {decision}, reason: {primary_reason}"
        )
        embedding = embed_text(text)
        index.upsert(
            vectors=[{
                "id": f"claim-{claim_id}",
                "values": embedding,
                "metadata": {
                    "text": text,
                    "decision": decision,
                    "claim_type": claim_type,
                    "amount": amount,
                    "source": "live_claim",
                },
            }],
            namespace=CLAIMS,
        )
    except Exception as e:
        logger.warning(f"Failed to index claim {claim_id}: {e}")
