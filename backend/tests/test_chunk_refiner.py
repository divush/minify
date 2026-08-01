from minify.chunk_refiner.llm_chunk_refiner import LLMChunkRefiner, _ChunkDecision, _RefinementResponse
from minify.chunker import RawChunk


class _FakeStructuredModel:
    def __init__(self, response: _RefinementResponse) -> None:
        self._response = response
        self.prompts: list[str] = []

    def invoke(self, prompt: str) -> _RefinementResponse:
        self.prompts.append(prompt)
        return self._response


class _FailingStructuredModel:
    def invoke(self, prompt: str):
        raise RuntimeError("api boom")


class _FakeChatModel:
    def __init__(self, response: _RefinementResponse | None = None, should_fail: bool = False) -> None:
        self._response = response
        self._should_fail = should_fail
        self.structured_calls: list[type] = []
        self.last_structured_model: _FakeStructuredModel | _FailingStructuredModel | None = None

    def with_structured_output(self, schema: type):
        self.structured_calls.append(schema)
        model = _FailingStructuredModel() if self._should_fail else _FakeStructuredModel(self._response)
        self.last_structured_model = model
        return model


class _FakeChatModelFactory:
    def __init__(self, model: _FakeChatModel) -> None:
        self._model = model
        self.requested_models: list[str | None] = []

    def get_chat_model(self, model: str | None = None):
        self.requested_models.append(model)
        return self._model


def _decisions(**by_index: str) -> _RefinementResponse:
    return _RefinementResponse(
        decisions=[_ChunkDecision(index=i, action=action) for i, action in by_index.items()]
    )


def _chunk(heading: str, text: str, page_start: int, page_end: int) -> RawChunk:
    return RawChunk(heading=heading, text=text, page_start=page_start, page_end=page_end)


def test_requests_the_configured_refinement_model():
    factory = _FakeChatModelFactory(_FakeChatModel(_decisions(**{"0": "keep", "1": "keep"})))
    refiner = LLMChunkRefiner(factory, model="gpt-cheap")

    refiner.refine([_chunk("A", "a", 1, 1), _chunk("B", "b", 2, 2)])

    assert factory.requested_models == ["gpt-cheap"]


def test_all_keep_is_a_noop():
    chunks = [_chunk("A", "a", 1, 1), _chunk("B", "b", 2, 2)]
    factory = _FakeChatModelFactory(_FakeChatModel(_decisions(**{"0": "keep", "1": "keep"})))

    result = LLMChunkRefiner(factory).refine(chunks)

    assert result == chunks


def test_merge_folds_forward_into_next_keep():
    chunks = [_chunk("Part I", "empty divider", 1, 1), _chunk("Chapter 1", "real content", 2, 10)]
    factory = _FakeChatModelFactory(_FakeChatModel(_decisions(**{"0": "merge", "1": "keep"})))

    result = LLMChunkRefiner(factory).refine(chunks)

    assert len(result) == 1
    assert result[0].heading == "Chapter 1"
    assert result[0].text == "empty divider\n\nreal content"
    assert result[0].page_start == 1
    assert result[0].page_end == 10


def test_trailing_merge_run_folds_backward_into_last_kept():
    chunks = [
        _chunk("Chapter 9", "real content", 1, 20),
        _chunk("A", "aardvark", 21, 21),
        _chunk("B", "banana", 22, 22),
    ]
    factory = _FakeChatModelFactory(
        _FakeChatModel(_decisions(**{"0": "keep", "1": "merge", "2": "merge"}))
    )

    result = LLMChunkRefiner(factory).refine(chunks)

    assert len(result) == 1
    assert result[0].heading == "Chapter 9"
    assert result[0].text == "real content\n\naardvark\n\nbanana"
    assert result[0].page_start == 1
    assert result[0].page_end == 22


def test_drop_removes_chunk_entirely():
    chunks = [_chunk("Copyright", "legal boilerplate", 1, 1), _chunk("Chapter 1", "real content", 2, 10)]
    factory = _FakeChatModelFactory(_FakeChatModel(_decisions(**{"0": "drop", "1": "keep"})))

    result = LLMChunkRefiner(factory).refine(chunks)

    assert [c.heading for c in result] == ["Chapter 1"]


def test_missing_index_defaults_to_keep():
    chunks = [_chunk("A", "a", 1, 1), _chunk("B", "b", 2, 2)]
    # Response only mentions index 1 -- index 0 should default to "keep".
    factory = _FakeChatModelFactory(_FakeChatModel(_decisions(**{"1": "keep"})))

    result = LLMChunkRefiner(factory).refine(chunks)

    assert [c.heading for c in result] == ["A", "B"]


def test_exception_falls_back_to_original_chunks():
    chunks = [_chunk("A", "a", 1, 1), _chunk("B", "b", 2, 2)]
    factory = _FakeChatModelFactory(_FakeChatModel(should_fail=True))

    result = LLMChunkRefiner(factory).refine(chunks)

    assert result == chunks


def test_degenerate_response_leaving_nothing_kept_falls_back_to_original():
    chunks = [_chunk("A", "a", 1, 1), _chunk("B", "b", 2, 2)]
    factory = _FakeChatModelFactory(_FakeChatModel(_decisions(**{"0": "drop", "1": "drop"})))

    result = LLMChunkRefiner(factory).refine(chunks)

    assert result == chunks


def test_fewer_than_two_chunks_skips_the_llm_call_entirely():
    chunks = [_chunk("A", "a", 1, 1)]
    factory = _FakeChatModelFactory(_FakeChatModel())

    result = LLMChunkRefiner(factory).refine(chunks)

    assert result == chunks
    assert factory.requested_models == []


def test_prompt_includes_heading_page_count_and_snippet():
    chunks = [_chunk("Chapter 1", "This is the opening line of the chapter.", 5, 12)]
    chunks = [chunks[0], _chunk("B", "b", 13, 13)]
    fake_model = _FakeChatModel(_decisions(**{"0": "keep", "1": "keep"}))
    factory = _FakeChatModelFactory(fake_model)

    LLMChunkRefiner(factory).refine(chunks)

    prompt = fake_model.last_structured_model.prompts[0]
    assert "Chapter 1" in prompt
    assert "8 page(s)" in prompt  # pages 5-12 inclusive
    assert "This is the opening line of the chapter." in prompt
