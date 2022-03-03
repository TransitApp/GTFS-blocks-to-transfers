import pytest
from pathlib import Path
import tempfile
import shutil
import blocks_to_transfers.__main__

TEST_DIR = Path(__file__).parent.resolve()
WORK_DIR = TEST_DIR / '.work'
WORK_DIR.mkdir(exist_ok=True)

def find_tests():
    test_dirs = []
    for dirent in TEST_DIR.iterdir():
        if dirent.is_dir() and dirent.name.startswith('test_'):
            test_dirs.append(dirent)
    return test_dirs


def check_file(expected_filename, actual_filename):
    with open(actual_filename) as actual_fp:
        with open(expected_filename) as expected_fp:
            actual_text = actual_fp.readlines()
            expected_text = expected_fp.readlines()
            assert actual_text == expected_text

   
@pytest.mark.parametrize('feed_dir', find_tests(), ids=lambda test_dir: test_dir.name)
@pytest.mark.parametrize('simplification', ('standard', 'linear'))
def test_default(feed_dir, simplification):
    work_dir = Path(tempfile.mkdtemp(prefix='', dir=WORK_DIR))

    for filename in (TEST_DIR / 'base').iterdir():
        shutil.copy2(filename, work_dir / filename.name)

    for filename in (feed_dir / 'input').iterdir():
        shutil.copy2(filename, work_dir / filename.name)

    print(f'Testing feed in {work_dir}')
   
    blocks_to_transfers.__main__.process(work_dir, work_dir, use_simplify_linear=(simplification == 'linear'))

    for expected_filename in (feed_dir / f'expected_{simplification}').iterdir():
        actual_filename = work_dir / expected_filename.name
        check_file(expected_filename, actual_filename)

    shutil.rmtree(work_dir)
