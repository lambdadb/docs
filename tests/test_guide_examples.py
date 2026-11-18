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
        examples = blocks("guides/collections/native-embeddings.mdx")
        schemas = [example["indexConfigs"] for example in examples if "indexConfigs" in example]
        self.assertEqual(2, len(schemas))
        for schema in schemas:
            validate(SPEC["components"]["schemas"]["IndexConfigs"], schema)
        queries = [example for example in examples if "query" in example]
        self.assertEqual([REQUEST["examples"][name]["value"] for name in
                          ("nativeEmbeddingKnnQuery", "cohereMultimodalKnnQuery")], queries)
        for query in queries:
            validate(REQUEST["schema"], query)

    def test_data_versioning_guide_matches_spec(self):
        base = "/collections/{collectionName}"

        def body(path, method, code=None):
            operation = SPEC["paths"][base + path][method]
            content = operation["requestBody"] if code is None else operation["responses"][code]
            return content["content"]["application/json"]["schema"]

        examples = blocks("guides/data-versioning/branches-tags-aliases.mdx")
        for key, path in (("branch", "/branches/{branchName}"), ("tag", "/tags/{tagName}"),
                          ("alias", "/aliases/{aliasName}")):
            responses = [example for example in examples if isinstance(example.get(key), dict)]
            self.assertEqual(1, len(responses), key)
            # One ref has one shape: its read, its creation and each entry of its listing.
            validate(body(path, "get", "200"), responses[0])
            validate(body("/" + key + ("es" if key != "tag" else "s"), "post", "201"), responses[0])
        creations = [example for example in examples if "branchName" in example]
        self.assertEqual(2, len(creations))
        for creation in creations:
            validate(body("/branches", "post"), creation)

    def test_collection_creation_guide_matches_spec(self):
        created = [example for example in blocks("guides/collections/create-a-collection.mdx")
                   if "projectName" in example.get("collection", {})]
        self.assertEqual(1, len(created))
        validate(SPEC["paths"]["/collections"]["post"]["responses"]["201"]["content"]["application/json"]["schema"],
                 created[0])

