from citeproof.normalize import normalize_entry
from citeproof.parse import parse_bibtex
from citeproof.pipeline import parse_job


SAMPLE = """@inproceedings{vaswani2017attention,
  title={Attention Is All You Need},
  author={Vaswani, Ashish and Shazeer, Noam},
  booktitle={NeurIPS},
  year={2017}
}

@article{x,
  title = "BERT: Pre-training",
  author = "Devlin, Jacob and Chang, Ming-Wei",
  year = 2018,
  eprint = {1810.04805},
  doi = {https://doi.org/10.18653/v1/N19-1423}
}
"""


def test_parse_and_ids():
    entries = parse_bibtex(SAMPLE)
    assert len(entries) == 2
    a = normalize_entry(entries[0])
    assert a["title"] == "Attention Is All You Need"
    assert a["author_last_names"] == ["vaswani", "shazeer"]
    assert a["year"] == 2017
    b = normalize_entry(entries[1])
    assert b["arxiv_id"] == "1810.04805"
    assert b["doi"] == "10.18653/v1/n19-1423"


def test_nested_braces():
    entry = parse_bibtex("@misc{k, title={{BERT}: Hello}, author={Doe, Jane}, year={2020}}")[0]
    assert normalize_entry(entry)["title"] == "BERT: Hello"


def test_parse_job_rejects_empty():
    try:
        parse_job("   ")
        assert False
    except ValueError as err:
        assert "BibTeX" in str(err)
