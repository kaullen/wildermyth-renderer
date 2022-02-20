import os

import setuptools

setup_dir = os.path.abspath(os.path.dirname(__file__))

with open(os.path.join(setup_dir, 'README.md'), encoding='utf-8') as fh:
    readme = fh.read().strip()

setuptools.setup(
    name="wildermyth_renderer",
    version='0.0.1',
    description="Wildermyth relationship chart renderer",
    long_description=readme,
    long_description_content_type="text/markdown",
    url="https://github.com/KaulleN/wildermyth-renderer",
    author="KaulleN",
    maintainer="KaulleN",
    packages=setuptools.find_packages(),
    python_requires='>=3.8',
    install_requires=[
        'graphviz==0.19.1',
        'Pillow==9.0.1',
    ],
)
