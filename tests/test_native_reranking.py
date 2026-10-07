"""Run with: uv run --with jsonschema python -B -m unittest discover -s tests -v.

The static OpenAPI is this repository's source for the API reference. These
checks cover compatibility, response envelopes, and shared public examples;
field lookup, UTF-8 budgets, and cross-field size validation remain server checks.
"""

import copy
import json
import re
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SPEC = json.loads((ROOT / "reference/api/openapi.json").read_text())
QUERY = SPEC["paths"]["/collections/{collectionName}/query"]["post"]
REQUEST = QUERY["requestBody"]["content"]["application/json"]
RESPONSE = QUERY["responses"]["200"]["content"]["application/json"]


def validator(schema):
    # Retain the document's components for local refs in extracted schemas.
    return Draft202012Validator({"components": SPEC["components"], **schema})


class NativeRerankingContractTest(unittest.TestCase):
    def setUp(self):
        self.request = copy.deepcopy(REQUEST["examples"]["nativeReranking"]["value"])
        self.response = copy.deepcopy(RESPONSE["examples"]["customReranking"]["value"])
        self.requests = validator(REQUEST["schema"])
        self.responses = validator(RESPONSE["schema"])

    def test_all_reference_and_guide_examples_validate(self):
        for example in REQUEST["examples"].values():
            with self.subTest(request=example["summary"]):
                self.requests.validate(example["value"])
        for example in RESPONSE["examples"].values():
            with self.subTest(response=example["summary"]):
                body = example["value"]
                self.responses.validate(body)
                if body["docs"]:
                    scores = [item["score"] for item in body["docs"]]
                    self.assertEqual(max(scores), body["maxScore"])
                    self.assertEqual(sorted(scores, reverse=True), scores)
                if body.get("rerank", {}).get("status") == "applied":
                    self.assertEqual(
                        body["rerank"]["candidateCount"], body["rerank"]["scoredCount"]
                    )
        guide = (ROOT / "guides/search/native-reranking.mdx").read_text()
        blocks = [
            json.loads(value)
            for value in re.findall(r"```json\n(.*?)\n```", guide, re.DOTALL)
        ]
        expected = [
            REQUEST["examples"][name]["value"]
            for name in ("nativeReranking", "customReranking")
        ] + [
            RESPONSE["examples"][name]["value"]
            for name in (
                "nativeReranking",
                "customReranking",
                "emptyReranking",
                "rerankFallback",
            )
        ]
        self.assertEqual(expected, blocks)

    def test_legacy_and_optional_null_requests_remain_valid(self):
        for body in (
            {},
            {"rerank": None},
            {"size": None},
            {"size": 0, "facets": {"tags": {}}},
            {"sort": [{"title": "asc"}], "rerank": None},
        ):
            self.requests.validate(body)
        for field in ("candidateSize", "onFailure", "criteria"):
            body = copy.deepcopy(self.request)
            body["rerank"][field] = None
            self.requests.validate(body)
        self.request["size"] = None
        self.request["sort"] = None
        self.requests.validate(self.request)
        self.assertNotIn("default", SPEC["components"]["schemas"]["RerankConfig"])
        self.assertNotIn(
            "default",
            SPEC["components"]["schemas"]["RerankConfig"]["properties"][
                "candidateSize"
            ],
        )

    def test_rerank_requires_query_positive_size_and_no_sort(self):
        for update in (
            {"size": 0, "facets": {"tags": {}}},
            {"query": None},
            {"sort": []},
            {"sort": [{"title": "asc"}]},
        ):
            with self.subTest(update=update):
                self.assertFalse(self.requests.is_valid({**self.request, **update}))
        del self.request["query"]
        self.assertFalse(self.requests.is_valid(self.request))
        # Query semantics and candidateSize >= size require runtime validation;
        # the schema does not pretend to implement those checks dynamically.

    def test_required_provider_model_and_reject_unsupported_options(self):
        for field in ("provider", "model", "queryText", "fields"):
            body = copy.deepcopy(self.request)
            del body["rerank"][field]
            self.assertFalse(self.requests.is_valid(body), field)
        for field, value in (
            ("provider", "cohere"),
            ("model", "unknown"),
            ("weights", [0, 1]),
            ("threshold", 0.5),
            ("apiKey", "not-a-supported-option"),
        ):
            body = copy.deepcopy(self.request)
            body["rerank"][field] = value
            self.assertFalse(self.requests.is_valid(body), field)

    def test_field_criteria_and_candidate_bounds(self):
        invalid = (
            ("fields", []),
            ("fields", ["body"] * 2),
            ("fields", [f"field{i}" for i in range(9)]),
            ("fields", [" "]),
            ("queryText", ""),
            ("queryText", " \t"),
            ("candidateSize", 0),
            ("candidateSize", 101),
            ("candidateSize", 50.5),
            ("onFailure", "ignore"),
            ("criteria", []),
            ("criteria", ["one"]),
            ("criteria", ["same", "same"]),
            ("criteria", ["one", " "]),
            ("criteria", ["one", None]),
            ("criteria", [{}, {}]),
            ("criteria", [str(i) for i in range(11)]),
        )
        for field, value in invalid:
            body = copy.deepcopy(self.request)
            body["rerank"][field] = value
            self.assertFalse(self.requests.is_valid(body), (field, value))
        for count in (2, 3, 10):
            self.request["rerank"]["criteria"] = [f"Level {i}" for i in range(count)]
            self.requests.validate(self.request)

    def test_zero_precision_and_score_envelope(self):
        self.responses.validate(self.response)
        self.assertEqual(0, self.response["docs"][1]["score"])
        for item in self.response["docs"]:
            self.assertIn("retrievalScore", item)
            self.assertNotIn("retrievalScore", item["doc"])
        self.response["docs"][0]["score"] = 0.80000002
        self.response["maxScore"] = 0.80000002
        decoded = json.loads(json.dumps(self.response))
        self.assertEqual(0.80000002, decoded["docs"][0]["score"])
        self.responses.validate(decoded)
        self.response["docs"][0]["score"] = 1.01
        self.assertFalse(self.responses.is_valid(self.response))
        self.assertNotIn(
            "format",
            RESPONSE["schema"]["properties"]["docs"]["items"]["properties"]["score"],
        )

    def test_skip_and_fallback_metadata_do_not_leak_partial_scores(self):
        for name in ("emptyReranking", "rerankFallback"):
            body = copy.deepcopy(RESPONSE["examples"][name]["value"])
            self.responses.validate(body)
            metadata = body["rerank"]
            self.assertEqual(0, metadata["scoredCount"])
            self.assertNotIn("criteriaVersion", metadata)
            self.assertTrue(all("retrievalScore" not in item for item in body["docs"]))
            for update in ({"scoredCount": 1}, {"criteriaVersion": "custom"}):
                broken = copy.deepcopy(body)
                broken["rerank"].update(update)
                self.assertFalse(self.responses.is_valid(broken))
        self.assertNotIn("maxScore", RESPONSE["examples"]["emptyReranking"]["value"])
        self.assertGreater(
            RESPONSE["examples"]["rerankFallback"]["value"]["maxScore"], 1
        )

    def test_optional_metadata_and_offloaded_scores(self):
        for field in ("resolvedModel", "criteriaVersion"):
            self.response["rerank"].pop(field, None)
        self.responses.validate(self.response)
        body = copy.deepcopy(self.response)
        body.update(
            isDocsInline=False, docs=[], docsUrl="https://example.com/results.json"
        )
        self.responses.validate(body)
        self.assertIn("rerank", body)
        for field in ("rerankScore", "rubricVersion"):
            self.assertNotIn(
                field, SPEC["components"]["schemas"]["RerankResponse"]["properties"]
            )
        self.assertNotIn(
            "rerankScore",
            RESPONSE["schema"]["properties"]["docs"]["items"]["properties"],
        )


if __name__ == "__main__":
    unittest.main()
