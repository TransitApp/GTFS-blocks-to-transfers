import pytest
from gtfs_loader import test_support
import blocks_to_transfers.__main__


test_support.init(__file__)


@pytest.mark.parametrize('feed_dir',
                         test_support.find_tests('standard'),
                         ids=lambda test_dir: test_dir.name)
def test_standard(feed_dir):
    do_test(feed_dir, 'standard')


@pytest.mark.parametrize('feed_dir',
                         test_support.find_tests('linear'),
                         ids=lambda test_dir: test_dir.name)
def test_linear(feed_dir):
    do_test(feed_dir, 'linear')


def do_test(feed_dir, simplification):
    work_dir = test_support.create_test_data(feed_dir)

    blocks_to_transfers.__main__.process(
        work_dir, work_dir, 
        use_simplify_linear=(simplification == 'linear'),
        sorted_io=True)

    test_support.check_expected_output(feed_dir, work_dir, tag=simplification)
