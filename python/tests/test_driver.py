#!/usr/bin/env python3
import unittest
import logging
import freeconf.driver
import freeconf.parser
import freeconf.pb.fc_pb2

# Configure logging to show debug messages
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

class TestDriver(unittest.TestCase):

    def test_load(self):
        logging.debug("Starting test_load")
        d = freeconf.driver.Driver()
        d.load()
        d.g_handles.Release(freeconf.pb.fc_pb2.ReleaseRequest(hnd=2))
        d.g_handles.Release(freeconf.pb.fc_pb2.ReleaseRequest(hnd=3))
        d.g_handles.Release(freeconf.pb.fc_pb2.ReleaseRequest(hnd=4))
        d.g_handles.Release(freeconf.pb.fc_pb2.ReleaseRequest(hnd=5))
        d.g_handles.Release(freeconf.pb.fc_pb2.ReleaseRequest(hnd=6))
        d.unload()
        logging.debug("Completed test_load")

if __name__ == '__main__':
    unittest.main()
