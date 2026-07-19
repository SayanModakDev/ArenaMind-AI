from pydantic import ValidationError
from hypothesis import given, strategies as st
from schemas import QueryRequest

@given(st.text(max_size=2000))
def test_input_fuzzing(fuzzed_text):
    try:
        req = QueryRequest(query=fuzzed_text)
        assert req.query == fuzzed_text
    except ValidationError:
        # Pydantic gracefully handled the invalid input (e.g. too short)
        pass
