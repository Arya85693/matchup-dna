import random
import unittest

import numpy as np

from matchup_dna.interpret import explain, probability_effect
from matchup_dna.phase4_model import Phase4Logistic
from test_phase4_model import random_row


class ExplainTests(unittest.TestCase):
    def setUp(self):
        rng = random.Random(3)
        self.rows = [random_row(rng) for _ in range(300)]
        self.model = Phase4Logistic(("rank", "inactivity", "form", "serve_return"), l2=10.0).fit(self.rows)

    def test_terms_add_up_to_the_prediction(self):
        row = self.rows[0]
        terms, total = explain(self.model, row)
        self.assertAlmostEqual(sum(value for _, value in terms), total)
        p = self.model.predict([row])[0]
        self.assertAlmostEqual(1 / (1 + np.exp(-total)), p)

    def test_correlated_elo_inputs_are_one_line(self):
        terms, _ = explain(self.model, self.rows[1])
        labels = [label for label, _ in terms]
        self.assertEqual(labels.count("Elo ratings (overall and surface together)"), 1)
        self.assertEqual(len(labels), len(set(labels)))

    def test_probability_effect_near_even_odds(self):
        self.assertAlmostEqual(probability_effect(0.4, 0.5), 0.1)


if __name__ == "__main__":
    unittest.main()
