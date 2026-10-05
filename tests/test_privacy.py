import unittest
from teleassist.common.privacy import mask


class PrivacyTests(unittest.TestCase):
    def test_labelled_names_addresses_and_unlabelled_provider_key(self):
        fake_key='AIza'+'x'*35
        text="My name is Jane Smith. My address is 42 Example Road, Example City. "+fake_key
        masked,counts=mask(text)
        for private in ('Jane Smith','42 Example Road',fake_key):
            self.assertNotIn(private,masked)
        self.assertEqual(counts['NAME'],1)
        self.assertEqual(counts['ADDRESS'],1)
        self.assertEqual(counts['SECRET'],1)

    def test_typical_operational_text_is_preserved(self):
        text='The router name is HomeWifi. Subscriber ID verification is pending. Download speed is 100 Mbps.'
        self.assertEqual(mask(text)[0],text)
