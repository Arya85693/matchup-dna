"""Phase 5: clustered means and the tournament-date bootstrap (matchup_dna.uncertainty)."""
import math
import unittest

from matchup_dna import uncertainty


class UncertaintyTests(unittest.TestCase):
    def test_clustered_mean_and_interval(self):
        mean, se = uncertainty.clustered_mean([1.0, 2.0, 3.0, 4.0], [1, 1, 2, 2])
        self.assertEqual(mean, 2.5)
        self.assertGreater(se, 0)
        low, high, p = uncertainty.interval(mean, se)
        self.assertLess(low, mean)
        self.assertGreater(high, mean)
        self.assertTrue(0 <= p <= 1)

    def test_one_cluster_has_no_standard_error(self):
        _, se = uncertainty.clustered_mean([1.0, 2.0], [7, 7])
        self.assertTrue(math.isnan(se))

    def test_the_bootstrap_draws_whole_clusters_reproducibly(self):
        rows = [{"c": c, "v": v} for c, v in ((1, 1.0), (1, 1.0), (2, 5.0), (3, 9.0))]
        first = uncertainty.cluster_bootstrap(rows, lambda r: r["c"], lambda s: sum(r["v"] for r in s), draws=50)
        second = uncertainty.cluster_bootstrap(rows, lambda r: r["c"], lambda s: sum(r["v"] for r in s), draws=50)
        self.assertEqual(first, second)
        pairs = uncertainty.cluster_bootstrap(rows, lambda r: r["c"],
                                              lambda s: sum(r is rows[0] for r in s) - sum(r is rows[1] for r in s),
                                              draws=50)
        self.assertEqual(set(pairs), {0})  # cluster 1's two rows always travel together

    def test_percentile_interval(self):
        self.assertEqual(uncertainty.percentile_interval(list(range(101))), (2, 97))


if __name__ == "__main__":
    unittest.main()
