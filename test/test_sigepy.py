import unittest
from SIGEPy import *
from sample_data import *
from tempfile import TemporaryDirectory
from pathlib import Path
from random import randrange, choice
import json, pydash

SENDER_TEST = SENDER_TEST[list(SENDER_TEST.keys())[0]]
RECEIVER_TEST = RECEIVER_TEST[list(RECEIVER_TEST.keys())[0]]


class TestSigepy(unittest.TestCase):
    def setUp(self) -> None:
        self.s = SIGEPy(*SIGEPY_DATA.values())
        self.packs = PACKS_SERVICE

    def addPackages(self):
        for pack in self.packs:
            self.s.add_package(**pack)

    def configureAddress(self):
        self.s.create_sender(**SENDER_TEST)
        self.s.create_receiver(**RECEIVER_TEST)

    def closePostingList(self):
        self.addPackages()
        self.configureAddress()
        self.s.close_posting_list()

    def test_createSender(self):
        self.s.create_sender(**SENDER_TEST)
        self.assertIsNotNone(self.s.sender)

    def test_createReceiver(self):
        self.s.create_receiver(**RECEIVER_TEST)
        self.assertIsNotNone(self.s.receiver)

    def test_addPackages(self):
        self.addPackages()
        self.assertGreater(len(self.s.packages), 0)

    def test_closePostingList(self):
        self.closePostingList()
        self.assertIsNotNone(self.s.posting_list)

    def test_getUser(self):
        self.assertIsInstance(self.s.get_user(), User)

    def test_getPostingCardStatus(self):
        self.assertTrue(self.s.get_posting_card_status())

    def test_requestTrackingCodes(self):
        t = self.s.request_tracking_codes(SERVICE_PAC)
        self.assertTrue(all(isinstance(_, TrackingCode) for _ in t))

    def test_verifyServiceAvailability(self):
        self.closePostingList()
        status = self.s.verify_service_availability()
        self.assertTrue(status)

    def test_deliveryTime(self):
        self.closePostingList()
        self.assertTrue(all(int(d) > 0 for d in self.s.delivery_time))

    def test_calculateFreights(self):
        self.closePostingList()
        self.assertTrue(all(d.delivery_time > timedelta(days=0) for d in self.s.freights))

    def test_generateDeliveryLabelsPDF(self):
        self.closePostingList()
        dir = TemporaryDirectory()
        fp = Path(dir.name).joinpath('temp.pdf')
        self.s.generate_delivery_labels_pdf(fp.as_posix())
        self.assertTrue(fp.exists())
        dir.cleanup()

    def test_generatePostingListPDF(self):
        self.closePostingList()
        dir = TemporaryDirectory()
        fp = Path(dir.name).joinpath('temp.pdf')
        self.s.generate_delivery_posting_list_pdf(fp.as_posix())
        self.assertTrue(fp.exists())
        dir.cleanup()


@unittest.skip
class TestCEP(unittest.TestCase):

    def setUp(self) -> None:
        self.s = SIGEPy(*SIGEPY_DATA.values())

    def generate_zipcode(self, uf, qtd):
        uf_zipcode_range = data.ZIP_CODE_MAP[uf]
        zipcodes = []
        tries = 0
        while(len(zipcodes) < qtd):
            zip_left, zip_right = uf_zipcode_range

            zip_left = str(choice([randrange(r.start, r.stop, r.step) for r in zip_left.ranges]))[:5]
            zip_right = str(choice([randrange(r.start, r.stop, r.step) for r in zip_right.ranges]))[:3]

            zip_left = ''.join(['0'] * (5 - len(zip_left))) + zip_left
            zip_right = ''.join(['0'] * (3 - len(zip_left))) + zip_right

            zip_temp = ZipCode(zip_left + '-' + zip_right)
            try:
                self.s.find_zipcode(zip_temp)
                zipcodes.append(zip_temp)
                tries = 0
            except:
                tries += 1
                if tries == 500:
                    break

        return zipcodes

    def test_cep(self):
        zipcodes_data = {}
        for uf in pydash.keys(data.ZIP_CODE_MAP):
            zuf: ZipCode
            for zuf in self.generate_zipcode(uf, 3):
                for serv in pydash.keys(data.SERVICES):
                    av = self.s.verify_service_availability(self.s.posting_card,
                                                       serv,
                                                       Address(**SENDER_TEST).zip_code,
                                                       zuf
                                                       )
                    key = '%s.ok.%s-%s' if av else '%s.err.%s-%s'
                    key %= (uf, serv, data.SERVICES[serv]['description'])
                    key = key.upper()
                    val = pydash.get(zipcodes_data, key, [])
                    val.append(zuf.display())
                    pydash.update(zipcodes_data, key, val)

        with open('zip_map.json', 'w', encoding='utf8') as json_file:
            json.dump(zipcodes_data, json_file, ensure_ascii=False)
            json_file.close()
