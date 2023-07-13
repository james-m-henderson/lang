#!/usr/bin/env python3
import sys
import io
import unittest 
import freeconf.driver
import freeconf.parser
import freeconf.node
import freeconf.nodeutil.json as fcjson

sys.path.append(".")
import car


class TestJson(unittest.TestCase):

    def test_read_car_json(self):
        drv = freeconf.driver.Driver()
        drv.load()

        p = freeconf.parser.Parser(driver=drv)
        schema = p.load_module_file('testdata', 'car')
        app = car.Car()
        mgmt = car.manage(app)
        b = freeconf.node.Browser(schema, mgmt, driver=drv)
        root = b.root()
        cfg = root.find("?content=config")
        actual = fcjson.json_write_str(cfg, driver=drv)
        cfg.release()
        self.assertEqual('{"speed":0}', actual)
        root.release()

        drv.unload()
        
        # useful if test won't exit
        # dump_threads()

if __name__ == '__main__':
    unittest.main()
