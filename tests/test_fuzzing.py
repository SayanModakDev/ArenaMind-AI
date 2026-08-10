from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from schemas import QueryRequest


@given(st.text(max_size=2000))
def test_input_fuzzing(fuzzed_text):
    try:
        req = QueryRequest(query=fuzzed_text)
        assert req.query == fuzzed_text or (not fuzzed_text.strip() and len(req.query) > 0)
    except ValidationError:
        # Pydantic gracefully handled the invalid input
        pass
