"""Docs owns guide consistency; server owns API contract boundary tests."""
import json
from pathlib import Path
import re
import unittest

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SPEC = json.loads((ROOT / "reference/api/openapi.json").read_text())
QUERY = SPEC["paths"]["/collections/{collectionName}/query"]["post"]
REQUEST = QUERY["requestBody"]["content"]["application/json"]
RESPONSE = QUERY["responses"]["200"]["content"]["application/json"]


def blocks(path):
    return [json.loads(value) for value in re.findall(
        r"```json\n(.*?)\n```", (ROOT / path).read_text(), re.DOTALL)]


def validate(schema, value):
    Draft202012Validator({"components": SPEC["components"], **schema}).validate(value)


class GuideExampleTest(unittest.TestCase):
    def test_reranking_guide_matches_spec(self):
        expected = [REQUEST["examples"][name]["value"] for name in ("nativeReranking", "customReranking")]
        expected += [RESPONSE["examples"][name]["value"] for name in
                     ("nativeReranking", "customReranking", "emptyReranking", "rerankFallback")]
        self.assertEqual(expected, blocks("guides/search/native-reranking.mdx"))
        for example in expected[:2]:
            validate(REQUEST["schema"], example)
        for example in expected[2:]:
            validate(RESPONSE["schema"], example)

    def test_hybrid_guide_matches_spec(self):
        example = blocks("guides/search/hybrid.mdx")[0]
        self.assertEqual(REQUEST["examples"]["bayesianHybrid"]["value"], example)
        validate(REQUEST["schema"], example)

    def test_native_embedding_guide_matches_spec(self):
        example = blocks("guides/collections/native-embeddings.mdx")[0]
        validate(SPEC["components"]["schemas"]["IndexConfigs"], example["indexConfigs"])
