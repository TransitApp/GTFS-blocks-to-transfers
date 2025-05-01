# If you get any errors, run `pip install setuptools wheel twine`
rm -rf dist
python3 setup.py sdist bdist_wheel
TWINE_USERNAME=transit \
    TWINE_PASSWORD=`op read 'op://Shared/64ojrnriw5gmll4qtqebvtfwpe/password'` \
    TWINE_REPOSITORY_URL=https://pypi.transitapp.com:443 \
    twine upload dist/*
