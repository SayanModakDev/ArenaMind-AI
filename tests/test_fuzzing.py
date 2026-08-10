from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from schemas import QueryRequest


@given(st.text(max_size=2000))
def test_input_fuzzing(fuzzed_text):
    try:
        req = QueryRequest(query=fuzzed_text)
        assert req.query == fuzzed_text
    except ValidationError:
        # Pydantic gracefully handled the invalid input (e.g. too short)
        pass
