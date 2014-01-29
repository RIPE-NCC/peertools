
from web_utils import RouterData
from nose.tools import eq_

def test_router_data_json():
    rd = RouterData('fake')
    eq_({'peers': 0, 'host': 'fake', 'state': 'uninitiated', 'error': None}, rd._json())

