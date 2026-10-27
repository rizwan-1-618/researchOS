from datetime import UTC, date, timedelta

from app.algorithms.graph import communities, pagerank, shortest_path
from app.algorithms.ranking import reciprocal_rank_fusion, weighted_mean
from app.algorithms.transitions import TransitionError, assert_question_transition
from app.algorithms.vectors import cosine, mean_vector, normalize
from app.integrations.identifiers import canonical_arxiv_id, canonical_doi
from app.integrations.openalex import abstract_from_inverted_index
from app.models.enums import QuestionStatus
from app.services.analytics import reading_streak


def test_doi_and_arxiv_identifiers():
    assert canonical_doi("https://doi.org/10.1000/XYZ") == "10.1000/xyz"
    assert canonical_arxiv_id("https://arxiv.org/abs/2401.12345v2") == "2401.12345"
    assert canonical_arxiv_id("hep-th/9901001v1") == "hep-th/9901001"


def test_openalex_abstract_reconstruction():
    text = abstract_from_inverted_index({"world": [1], "Hello": [0]})
    assert text == "Hello world"


def test_vectors_and_ranking():
    left = normalize([1, 0, 0])
    right = normalize([1, 1, 0])
    assert cosine(left, right) > 0
    assert mean_vector([left, left]) == left
    assert weighted_mean([(0.5, None), (0.5, 0.4)]) == 0.4
    fused = reciprocal_rank_fusion([["a", "b"], ["b", "a"]], 1)
    assert fused[0][0] == "a"


def test_graph_algorithms():
    nodes = ["a", "b", "c"]
    edges = [("a", "b"), ("b", "c")]
    ranks = pagerank(nodes, edges)
    assert set(ranks) == set(nodes)
    groups = communities(nodes, edges)
    assert len(set(groups.values())) == 1
    assert shortest_path(nodes, edges, "a", "c") == ["a", "b", "c"]
    assert shortest_path(nodes, edges, "a", "missing") is None


def test_question_transitions():
    assert_question_transition(QuestionStatus.draft, QuestionStatus.investigating)
    try:
        assert_question_transition(QuestionStatus.draft, QuestionStatus.completed)
        raise AssertionError("expected rejection")
    except TransitionError:
        pass


def test_reading_streak():
    today = date(2026, 10, 27)
    days = {today - timedelta(days=offset) for offset in range(3)}
    assert reading_streak(days, today) == 3
    assert reading_streak({today - timedelta(days=2)}, today) == 0
