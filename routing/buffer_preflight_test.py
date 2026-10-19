import unittest

from buffer_preflight import assess


class BufferPreflightTests(unittest.TestCase):
    def test_input_counts_and_headroom_do_not_admit_a_graph_from_worker_memory_alone(self):
        measured = {"resourceCheckpoints": {"historyBuilt": {"workerMaxRssKiB": 100}}}
        counts = {"sourceNodes": 10, "sourceWays": 5, "wayEligibleDirectedSegments": 20, "historyStatesUpperBound": 21}
        candidate = {**counts, "sourceNodes": 20}
        result = assess(candidate, counts, measured, factor=1.25, cap=300000)
        self.assertEqual(result["workerEstimateWithHeadroomBytes"], 256000)
        self.assertTrue(result["workerEstimateFits"])
        self.assertFalse(result["fullGraphAdmitted"])
        self.assertEqual(result["decision"], "hold-for-import-export-accounting")
        result = assess(candidate, counts, measured, factor=1.25, cap=200000)
        self.assertFalse(result["workerEstimateFits"])
        self.assertEqual(result["decision"], "hold-for-worker-capacity")


if __name__ == "__main__": unittest.main()
