"""The corrected namespace guard distinguishes dormant links from connectivity."""
import unittest

from coarse_timing_input import PilotError
from run_timing_cache import validate_namespace


class NamespaceTests(unittest.TestCase):
    def test_dormant_kernel_tunnels_without_routes_are_allowed(self):
        validate_namespace({'lo': 73, 'gre0': 128, 'gretap0': 4098}, 'Iface Destination Gateway\n', '00000000 lo\n')

    def test_active_link_or_ipv4_route_is_rejected(self):
        with self.assertRaises(PilotError): validate_namespace({'lo': 73, 'eth0': 4099}, 'Iface Destination\n', '')
        with self.assertRaises(PilotError): validate_namespace({'lo': 73, 'gre0': 128}, 'Iface Destination\ngre0 00000000\n', '')

    def test_ipv6_route_or_missing_loopback_is_rejected(self):
        with self.assertRaises(PilotError): validate_namespace({'lo': 73}, 'Iface Destination\n', '00000000 gre0\n')
        with self.assertRaises(PilotError): validate_namespace({'gre0': 128}, 'Iface Destination\n', '')


if __name__ == '__main__':
    unittest.main()
