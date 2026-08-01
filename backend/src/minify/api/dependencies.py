"""FastAPI dependency wiring: the single place concrete adapters get
constructed, per design.md's "API layer is the only wiring point" rule.

Every provider below is a small `@lru_cache`-decorated function returning a
shared singleton — cheap and safe since every adapter built so far is
stateless aside from holding a reference to another already-shared adapter
(`SqliteRepository` only holds an `Engine`; `LangChainChatModelFactory`
lazily caches its own model internally). Providers chain via nested
`Depends(...)`, which is what lets tests override a single low-level
provider (e.g. `get_chat_model_factory`) and have every provider built on
top of it pick up the override automatically.
"""

from functools import lru_cache

from fastapi import Depends
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from minify.chat import Chat
from minify.chat.langchain_chat import LangChainChat
from minify.chunk_refiner import ChunkRefiner
from minify.chunk_refiner.llm_chunk_refiner import LLMChunkRefiner
from minify.chunk_refiner.passthrough_chunk_refiner import PassthroughChunkRefiner
from minify.chunker import Chunker
from minify.chunker.structural_chunker import StructuralChunker
from minify.config import get_settings
from minify.ingestion import Ingestor
from minify.ingestion.pymupdf_adapter import PyMuPdfIngestor
from minify.jobs import JobRunner
from minify.jobs.pipeline_runner import PipelineJobRunner
from minify.llm import ChatModelFactory
from minify.llm.langchain_factory import LangChainChatModelFactory
from minify.profile import ProfileService
from minify.profile.service import DefaultProfileService
from minify.sequencing import Sequencer
from minify.sequencing.plain_sequencer import PlainSequencer
from minify.storage import Repository
from minify.storage.sqlite_adapter import SqliteRepository
from minify.summarizer import Summarizer
from minify.summarizer.langchain_summarizer import LangChainSummarizer


@lru_cache
def get_engine() -> Engine:
    return create_engine(get_settings().database_url)


@lru_cache
def get_repository(engine: Engine = Depends(get_engine)) -> Repository:
    return SqliteRepository(engine)


@lru_cache
def get_chat_model_factory() -> ChatModelFactory:
    return LangChainChatModelFactory(get_settings())


@lru_cache
def get_profile_service(repository: Repository = Depends(get_repository)) -> ProfileService:
    return DefaultProfileService(repository)


@lru_cache
def get_ingestor() -> Ingestor:
    return PyMuPdfIngestor()


@lru_cache
def get_chunker() -> Chunker:
    return StructuralChunker()


@lru_cache
def get_chunk_refiner(factory: ChatModelFactory = Depends(get_chat_model_factory)) -> ChunkRefiner:
    if not get_settings().enable_chunk_refinement:
        return PassthroughChunkRefiner()
    return LLMChunkRefiner(factory)


@lru_cache
def get_summarizer(factory: ChatModelFactory = Depends(get_chat_model_factory)) -> Summarizer:
    return LangChainSummarizer(factory)


@lru_cache
def get_sequencer(summarizer: Summarizer = Depends(get_summarizer)) -> Sequencer:
    return PlainSequencer(summarizer)


@lru_cache
def get_chat(factory: ChatModelFactory = Depends(get_chat_model_factory)) -> Chat:
    return LangChainChat(factory)


@lru_cache
def get_job_runner(
    ingestor: Ingestor = Depends(get_ingestor),
    chunker: Chunker = Depends(get_chunker),
    chunk_refiner: ChunkRefiner = Depends(get_chunk_refiner),
    sequencer: Sequencer = Depends(get_sequencer),
    repository: Repository = Depends(get_repository),
) -> JobRunner:
    return PipelineJobRunner(ingestor, chunker, chunk_refiner, sequencer, repository)
