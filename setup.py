# Copyright (c) 2020 SRI International.  Use of this material is subject to the terms specified in the license located at /LICENSE.txt
#

import setuptools

with open('README.md') as f:
    readme = f.read()

with open('LICENSE.txt') as f:
    license = f.read()

with open('VERSION') as f:
    version = f.read()


setuptools.setup(
  name='valet',
  version=version,
  description='The Valet project',
  long_description=readme,
  url='https://sri.com',
  author='SRI International',
  install_requires=[
      "plac>=1.3.0",
      "spacy>=3.2.0"
  ],
  package_dir={"": "src"},
  packages=["valetrules", "nlpcore"],
  include_package_data=True,
  license=license,
  platforms='any'
)
