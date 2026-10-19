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
        configs.validate({"vector": {"type": "vector", "dimensions": 64}})
        configs.validate({"vector": {
            "type": "vector", "dimensions": 64, "managedEmbedding": False,
        }})
        for update in (
            {"managedEmbedding": False},
            {"dimensions": 64},
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

    def test_dense_vector_dimensions_and_metrics(self):
        configs = validator(SPEC["components"]["schemas"]["IndexConfigs"])
        embeddings = validator(SPEC["components"]["schemas"]["EmbeddingConfig"])
        native = {
            "provider": "openai",
            "model": "text-embedding-3-small",
            "sourceField": "body",
        }
        for dimensions in (64, 4096):
            for similarity in ("cosine", "euclidean"):
                with self.subTest(dimensions=dimensions, similarity=similarity):
                    configs.validate({"vector": {
                        "type": "vector", "dimensions": dimensions,
                        "similarity": similarity,
                    }})
        # Native dimensions also obey the model's upper limit on the server.
        for dimensions in (64, 1536):
            for similarity in ("cosine", "euclidean"):
                embeddings.validate({
                    **native, "dimensions": dimensions, "similarity": similarity,
                })
        for dimensions in (1, 63, 4097, 64.5, "64"):
            with self.subTest(dimensions=dimensions):
                self.assertFalse(configs.is_valid({"vector": {
                    "type": "vector", "dimensions": dimensions,
                }}))
                self.assertFalse(embeddings.is_valid({**native, "dimensions": dimensions}))
        for similarity in ("dot_product", "max_inner_product", "Cosine"):
            with self.subTest(similarity=similarity):
                self.assertFalse(configs.is_valid({"vector": {
                    "type": "vector", "dimensions": 64, "similarity": similarity,
                }}))
        for similarity in ("dot_product", "max_inner_product"):
            self.assertFalse(embeddings.is_valid({**native, "similarity": similarity}))
        # Dense restrictions do not remove the sparse vector field type.
        configs.validate({"sparse": {"type": "sparseVector"}})
