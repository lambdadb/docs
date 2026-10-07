"""Validate public input compatibility; query semantics remain server checks."""

import copy
import json
import re
import unittest

from test_native_reranking import REQUEST, ROOT, SPEC, validator


class BayesianNativeEmbeddingContractTest(unittest.TestCase):
    def test_bayesian_guide_request_and_candidate_budgets(self):
        requests = validator(REQUEST["schema"])
        guide = (ROOT / "guides/search/hybrid.mdx").read_text()
        example = json.loads(re.search(r"```json\n(.*?)\n```", guide, re.S)[1])
        self.assertEqual(REQUEST["examples"]["bayesianHybrid"]["value"], example)
        requests.validate(example)
        for value in (0, 101, 1.5, "30"):
            with self.subTest(candidate_size=value):
                self.assertFalse(requests.is_valid({**example, "candidateSize": value}))
        reranked = REQUEST["examples"]["bayesianReranking"]["value"]
        requests.validate(reranked)
        self.assertFalse(requests.is_valid({**reranked, "candidateSize": 30}))
        requests.validate({**reranked, "candidateSize": None})
        self.assertNotIn("default", REQUEST["schema"]["properties"]["candidateSize"])

    def test_native_legacy_and_caller_vector_configurations(self):
        configs = validator(SPEC["components"]["schemas"]["IndexConfigs"])
        guide = (ROOT / "guides/collections/native-embeddings.mdx").read_text()
        example = json.loads(re.search(r"```json\n(.*?)\n```", guide, re.S)[1])
        configs.validate(example["indexConfigs"])
        native = example["indexConfigs"]["bodyEmbedding"]
        configs.validate({"vector": native})
        configs.validate({"vector": {**native, "managedEmbedding": True}})
        configs.validate({"vector": {"type": "vector", "dimensions": 3}})
        configs.validate({"vector": {
            "type": "vector", "dimensions": 3, "managedEmbedding": False,
        }})
        for update in (
            {"managedEmbedding": False},
            {"dimensions": 3},
            {"similarity": "cosine"},
        ):
            with self.subTest(update=update):
                self.assertFalse(configs.is_valid({"vector": {**native, **update}}))
        legacy_without_embedding = {"type": "vector", "managedEmbedding": True}
        self.assertFalse(configs.is_valid({"vector": legacy_without_embedding}))
        for required in ("provider", "model", "sourceField"):
            broken = copy.deepcopy(native)
            del broken["embedding"][required]
            self.assertFalse(configs.is_valid({"vector": broken}))
