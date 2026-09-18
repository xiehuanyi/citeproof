from citeproof.match import author_overlap, decide, score_candidate, title_similarity

VASWANI = {
    "key": "v",
    "title": "Attention Is All You Need",
    "authors": ["Ashish Vaswani", "Noam Shazeer"],
    "year": 2017,
    "venue": "NeurIPS",
    "doi": None,
    "arxiv_id": None,
}


def test_titles():
    assert title_similarity("Attention Is All You Need", "Attention is All you Need") > 0.95
    assert title_similarity("Attention Is All You Need", "Channel Attention Is All You Need for Video Frame Interpolation") < 0.86


def test_authors():
    assert author_overlap(["Vaswani, Ashish"], ["Ashish Vaswani"]) == 1
    assert author_overlap(["Yann LeCun", "Geoffrey Hinton"], ["Ashish Vaswani", "Noam Shazeer"]) < 0.2


def test_verified():
    scored = score_candidate(
        VASWANI,
        {
            "source": "semanticscholar",
            "title": "Attention is All you Need",
            "authors": ["Ashish Vaswani", "Noam Shazeer", "Niki Parmar"],
            "year": 2017,
            "venue": "Neural Information Processing Systems",
            "doi": None,
            "arxiv_id": "1706.03762",
        },
    )
    d = decide(VASWANI, [scored], [{"id": "semanticscholar", "status": "ok"}, {"id": "dblp", "status": "ok"}, {"id": "arxiv", "status": "ok"}])
    assert d["verdict"] == "verified"


def test_wrong_year():
    ref = {**VASWANI, "year": 2014, "title": "Deep Residual Learning for Image Recognition", "authors": ["Kaiming He"], "venue": "CVPR"}
    scored = score_candidate(
        ref,
        {
            "source": "dblp",
            "title": "Deep Residual Learning for Image Recognition",
            "authors": ["Kaiming He", "Xiangyu Zhang", "Shaoqing Ren", "Jian Sun"],
            "year": 2016,
            "venue": "CVPR",
            "doi": None,
            "arxiv_id": None,
        },
    )
    d = decide(ref, [scored], [{"id": "dblp", "status": "ok"}, {"id": "semanticscholar", "status": "ok"}, {"id": "openalex", "status": "ok"}])
    assert d["verdict"] == "metadata_mismatch"
    assert d["type"] == "metadata_hallucination"


def test_franken():
    ref = {**VASWANI, "authors": ["Yann LeCun", "Geoffrey Hinton"], "year": 2021, "venue": "ICML"}
    scored = score_candidate(
        ref,
        {
            "source": "semanticscholar",
            "title": "Attention Is All You Need",
            "authors": ["Ashish Vaswani", "Noam Shazeer"],
            "year": 2017,
            "venue": "NeurIPS",
            "doi": None,
            "arxiv_id": "1706.03762",
        },
    )
    d = decide(ref, [scored], [{"id": "semanticscholar", "status": "ok"}])
    assert d["verdict"] == "metadata_mismatch"
    assert d["type"] == "franken_citation"


def test_invalid_doi():
    ref = {
        **VASWANI,
        "title": "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding",
        "authors": ["Jacob Devlin"],
        "year": 2019,
        "doi": "10.1038/s41586-021-03819-2",
    }
    scored = score_candidate(
        ref,
        {
            "source": "crossref",
            "title": "Highly accurate protein structure prediction with AlphaFold",
            "authors": ["John Jumper"],
            "year": 2021,
            "venue": "Nature",
            "doi": "10.1038/s41586-021-03819-2",
            "arxiv_id": None,
        },
    )
    d = decide(ref, [scored], [{"id": "crossref", "status": "ok"}])
    assert d["verdict"] == "metadata_mismatch"
    assert d["type"] == "invalid_identifier"


def test_not_found_is_not_automatic_fake_when_sources_error():
    ref = {**VASWANI, "title": "An Obscure Workshop Note on Widgets", "authors": ["Jane Doe"], "year": 1994, "venue": "Workshop"}
    d = decide(ref, [], [{"id": "crossref", "status": "error"}, {"id": "dblp", "status": "error"}, {"id": "semanticscholar", "status": "empty"}])
    assert d["verdict"] == "inconclusive"
