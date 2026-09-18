from citeproof.pipeline import verify_bibliography


def test_mocked_providers_verify():
    bib = """@inproceedings{vaswani2017attention,
      title={Attention Is All You Need},
      author={Vaswani, Ashish and Shazeer, Noam},
      booktitle={NeurIPS},
      year={2017}
    }"""
    providers = [
        {
            "id": "semanticscholar",
            "label": "Semantic Scholar",
            "resolve": lambda ref: [
                {
                    "source": "semanticscholar",
                    "title": "Attention is All you Need",
                    "authors": ["Ashish Vaswani", "Noam Shazeer"],
                    "year": 2017,
                    "venue": "NeurIPS",
                    "doi": None,
                    "arxiv_id": "1706.03762",
                    "url": "https://example.test/s2",
                }
            ],
        },
        {
            "id": "dblp",
            "label": "DBLP",
            "resolve": lambda ref: [
                {
                    "source": "dblp",
                    "title": "Attention is All you Need",
                    "authors": ["Ashish Vaswani", "Noam Shazeer"],
                    "year": 2017,
                    "venue": "NIPS",
                    "doi": None,
                    "arxiv_id": None,
                    "url": "https://example.test/dblp",
                }
            ],
        },
    ]
    out = verify_bibliography(bib, workers=1, providers=providers)
    assert out["summary"]["verified"] == 1
    assert out["results"][0]["verdict"] == "verified"
