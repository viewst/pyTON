from setuptools import setup
from pipenv.project import Project
from pipenv.utils import convert_deps_to_pip

pfile = Project(chdir=False).parsed_pipfile
requirements = convert_deps_to_pip(pfile['packages'], r=False)
test_requirements = convert_deps_to_pip(pfile['dev-packages'], r=False)

with open("README.md", "r") as fh:
    long_description = fh.read()


setup(
    author='Emelyanenko Kirill',
    name='pyTON',
    version='0.1.4',
    packages=['pyTON'],
    install_requires=requirements,
    package_data={
        'pyTON': [
            'distlib/darwin/*',
            'distlib/linux/*',
            'webserver/*'
        ]
    },
    zip_safe=True,
    tests_require=test_requirements,
    python_requires='>=3.7',
    classifiers=[
         "Development Status :: 3 - Alpha",
         "Intended Audience :: Developers",
         "Programming Language :: Python :: 3.7",
         "License :: Other/Proprietary License",
         "Topic :: Software Development :: Libraries"
    ],
    url="https://github.com/viewst/pyTON",
    description = "Python API for libtonlibjson (Telegram Open Network Light Client)",
    long_description_content_type="text/markdown",
    long_description=long_description,
)
